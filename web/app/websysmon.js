/*global Core,d3,cubism*/
(function () {
  "use strict";

  var CONFIGURATION = {
    height: 50,
    width: 960
  };

  Core.extend('d3', d3);
  Core.extend('cubism', cubism);

  Core.register('wsdatasource', function (sandbox) {
    return {
      init: function () {
        var wsUri = "ws://"+window.location.hostname+":9007/",
            ws = new WebSocket(wsUri),
            dataBuffer = { buffer: [] },
            width = CONFIGURATION.width;

        ws.onmessage = function (e) {
          var data = JSON.parse(e.data);

          if (data.data) {
            dataBuffer.buffer.push(data.data);

            if (dataBuffer.buffer.length > width) {
              dataBuffer.buffer = dataBuffer.buffer.slice(-width);
            }
            sandbox.notify({
              type: 'dataupdate',
              data: {
                data: data.data,
                dataBuffer: dataBuffer
              }
            });
          }

          if (data.configuration) {
            sandbox.notify({
              type: 'configuration',
              data: data.configuration
            });
          }
        };
      }
    };
  });

  Core.register('cubismgraph', function (sandbox) {
    var cubism = sandbox.x('cubism'),
        d3 = sandbox.x('d3'),
        dataBuffer = { buffer: [] },
        width = CONFIGURATION.width, // TODO
        height = CONFIGURATION.height, // TODO
        context = cubism.context()
          .serverDelay(0)
          .clientDelay(0)
          .step(1e3)
          .size(width);

    return {
      init: function () {
        sandbox.listen('configuration', this.configure.bind(this));
        sandbox.listen('dataupdate', this.dataupdate.bind(this));
      },
      getMetric: function (dataBuffer, key, index) {
        return context.metric(function (start, stop, step, callback) {
          var values, qValues = [], quant, dataStart, dataStop, current;

          dataStart = start = +start;
          dataStop = stop = +stop;

          values = dataBuffer.buffer.filter(function (d) {
            return +d[key].timestamp >= start && +d[key].timestamp <= stop;
          });

          if (values.length) {
            dataStart = +values[0][key].timestamp;
            dataStop = +values[values.length - 1][key].timestamp;
          }

          values = values.map(function (d) {
            return (d[key].values && d[key].values.length) ? d[key].values[index || 0] : (d[key].values || 0);
          });

          quant = d3.scale.quantize().domain([dataStart, dataStop]).range(values);

          for (current = start; current <= stop; current += step) {
            if (current + step >= dataStart && current - step <= dataStop) {
              qValues.push(quant(current) || NaN);
            } else {
              qValues.push(NaN);
            }
          }

          callback(null, qValues);
        }, key + (index === undefined ? "" : index));
      },
      dataupdate: function (d) {
        if (d.dataBuffer) {
          dataBuffer.buffer = d.dataBuffer.buffer;
        }
      },
      configure: function (configuration) {
        var widget = this;

        d3.select(this.el).call(function(div) {

          div.attr("class", "cubism");

          div.append("div")
              .attr("class", "axis")
              .call(context.axis().orient("top"));

          Object.keys(configuration).forEach(function (key) {
            var metrics = [], i, graph, conf = configuration[key];

            if (conf.valueCount > 1) {
              for (i = 0; i < conf.valueCount; i++) {
                metrics.push(widget.getMetric(dataBuffer, conf.name, i));
              }
            } else {
              metrics.push(widget.getMetric(dataBuffer, conf.name));
            }

            graph = context.horizon().height(height * (conf.height || 1));

            if (conf.extent) {
              graph = graph.extent(conf.extent);
            }
            if (conf.colors) {
              graph = graph.colors(conf.colors);
            }

            div.selectAll(".horizon-"+key)
                .data(metrics)
              .enter().append("div")
                .attr("class", "horizon horizon-"+key)
                .call(graph);
          });

          div.append("div")
              .attr("class", "rule")
              .call(context.rule());

        });
      }
    };
  });

  Core.register('d3gauge', function (sandbox) {
    var d3 = sandbox.x('d3'),
        dataBuffer = { buffer: [] },
        currentData = {},
        width = 400,
        height = 400,
        key = 'cpu'; // TODO

    var interpolateHsl = function (a, b) {
      var i = d3.interpolateString(a, b);
      return function (t) {
        return d3.hsl(i(t));
      };
    };

    return {
      configuration: {},
      init: function () {
        sandbox.listen('configuration', this.configure.bind(this));
        sandbox.listen('dataupdate', this.dataupdate.bind(this));
      },
      configure: function (configuration) {
        var itemNum;

        this.configuration = configuration[key]; // TODO
        itemNum = this.configuration.valueCount;

        this.color = d3.scale.linear()
          .range(["hsl(80, 50%, 50%)", "hsl(0, 50%, 50%)"])
          .interpolate(interpolateHsl);

        this.arc = d3.svg.arc()
          .startAngle(Math.PI)
          .endAngle(function (d) { return ( d.value/100 * 1.5 + 1 ) * Math.PI; })
          .innerRadius(function (d) { return (width/2)/itemNum * d.index; })
          .outerRadius(function (d) { return (width/2)/itemNum * (d.index+1); });
        
        this.arcTween = function (d) {
          var i = d3.interpolateNumber(d.previousValue, d.value);
          return function (t) { d.value = i(t); return this.arc(d); }.bind(this);
        };

        // TODO
        this.svg = d3.select(this.el).append("svg")
            .attr("width", width)
            .attr("height", height)
          .append("g")
            .attr("transform", "translate(" + width / 2 + "," + height / 2 + ")");

        this.field = this.svg.selectAll("g")
            .data(this.getData.bind(this))
          .enter().append("g");

        this.field.append("path");

        d3.transition().duration(0).each(this.update.bind(this));
      },
      getData: function () {
        return currentData[key] ? currentData[key].values.map(function (v, i) {
          return {
            value: v,
            index: i
          };
        }) : (function (l) {
          var i, arr = [];
          for (i = 0; i < l; i++) {
            arr.push({value: 0, index: i});
          }
          return arr;
        }(this.configuration.valueCount)); // TODO
      },
      update: function () {
        this.field = this.field
            .each(function (d) { this._value = d.value; })
          .data(this.getData.bind(this))
            .each(function (d) { d.previousValue = this._value; });

        this.field.select("path")
          .transition()
            .ease("cubic-in-out")
            .attrTween("d", this.arcTween.bind(this))
            .style("fill", function (d) { return this.color(d.value/100); }.bind(this));
      },
      dataupdate: function (d) {
        if (d.dataBuffer) {
          dataBuffer.buffer = d.dataBuffer.buffer;
        }
        if (d.data) {
          currentData = d.data;
        }
        this.update();
      }
    };
  });

  Core.start('wsdatasource');
  Core.start('cubismgraph');
  Core.start('d3gauge');

/* normal d3 charts */
/*
var dataBuffer = CONFIGURATION.dataBuffer,
    width = CONFIGURATION.width,
    height = CONFIGURATION.height;

var configure_line = function (configuration) {
  d3.select("#line").call(function(div) {
    div.attr('class', 'd3line');

    var delay = 1000;

    var redraw = function (graph, line, key, xScale) {
      var animStart = 0, animStop = 0;

      // TODO !!!
      xScale.domain(d3.extent(dataBuffer.buffer, function(d) { return new Date(d[key].timestamp); }));

      if (dataBuffer.buffer.length > 2) {
        animStart = xScale(new Date(dataBuffer.buffer[1][key].timestamp));
        animStop = xScale(new Date(dataBuffer.buffer[0][key].timestamp));
      }

      graph.selectAll('path')
        .data([dataBuffer.buffer])
        .attr('transform', 'translate('+animStart+')')
        .attr('d', line)
        .transition()
        .ease('linear')
        .duration(delay*.9)
        .attr('transform', 'translate('+animStop+')');
    };

    Object.keys(configuration).forEach(function (key) {
      var graph = div.append('svg:svg')
            .attr('width', width)
            .attr('height', height * 5);

      var xScale = d3.time.scale()
            .range([0, width]);

      var yScale = d3.scale.linear()
            .range([height * 5, 0])
            .domain(configuration[key].extent || [0, 100]);

      var line = d3.svg.line()
          .x(function (d, i) {
            return xScale(new Date(d[key].timestamp));
          })
          .y(function (d, i) {
            return yScale((d[key].values && d[key].values.length) ? d[key].values[0] : (d[key].values || 0));
          })
          .interpolate('linear');

      graph.append('svg:path').attr('d', line(dataBuffer.buffer));

      setInterval(function () {
        redraw(graph, line, key, xScale);
      }, delay);
    });

  });
};
*/
/* normal d3 charts end */


}());
