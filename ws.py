#!/usr/bin/env python

import asyncio
import psutil
import simplejson
import time
import os
import whisper
from ws4py.async_websocket import WebSocket
from ws4py.server.tulipserver import WebSocketProtocol

from serial_sensors import get_value

websockets = []
probes = []


class Probe():

    DEFAULT_ARCHIVE_LIST = [
        '1:3600', # 1 sec per data for an hour
        '1m:6h',  # 1 min per data for 6 hours
        '1h:31d', # 1 hour per data for a month
        '6h:2y'   # 6 hours per data for two years
    ]

    def __init__(self, name, valueCount=1, rrdFileName=None, rrdRoot=None,
                 xFilesFactor=0.5, aggregationMethod='average', archiveList=None,
                 minMeasureInterval=0.9):
        self.name = name
        self.valueCount = valueCount
        self.minMeasureInterval = minMeasureInterval
        self.xFilesFactor = xFilesFactor
        self.aggregationMethod = aggregationMethod
        self.archiveList = [whisper.parseRetentionDef(retDef) for retDef
                            in (archiveList if archiveList else Probe.DEFAULT_ARCHIVE_LIST)]

        if rrdRoot is None:
            rrdRoot = os.path.dirname(os.path.realpath(__file__))
        if rrdFileName is None:
            rrdFileName = type(self).__name__ + "_" + self.name.replace(" ", "_")


        self.rrdFilePrefix = os.path.join(rrdRoot, rrdFileName)

        # create rrd files if they don't exist yet
        self.create_rrd_files()

        self._lastMeasurement = None

    def get_aggregationMethod(self, postfix):
        return self.aggregationMethod

    def create_rrd_files(self, overwrite=False):
        for i in range(0, self.valueCount):
            self.create_rrd_file(i, overwrite)

    def create_rrd_file(self, postfix, overwrite=False):
        path = self.get_rrd_file(postfix)

        if os.path.exists(path) and not overwrite:
            return

        whisper.create(path, self.archiveList, self.xFilesFactor,
                       self.get_aggregationMethod(postfix))

    def update_rrds(self, timestamp, values):
        for i in range(0, self.valueCount):
            self.update_rrd(i, timestamp, values[i])

    def update_rrd(self, postfix, timestamp, value):
        if value is not None:
            path = self.get_rrd_file(postfix)

            whisper.update(path, value, timestamp / 1000)

    def get_rrd_file(self, postfix=None):
        return self.rrdFilePrefix + str(postfix if postfix else "") + ".wrrd"

    def get_values(self):
        raise NotImplementedError()

    def get_configuration(self):
        raise NotImplementedError()

    def get_ts(self):
        return int(time.time() * 1000)

    def do_measure(self):
        values = self.get_values()
        ts = self.get_ts()

        self.update_rrds(ts, values)

        measurement = {
            "values": values,
            "timestamp": ts
        }

        self._lastMeasurement = measurement

        return measurement

    def get_data(self):
        ts = self.get_ts()

        if not self._lastMeasurement or self._lastMeasurement["timestamp"] + self.minMeasureInterval * 1000 < ts:
            measurement = self.do_measure()
        else:
            measurement = self._lastMeasurement

        return measurement


class CpuProbe(Probe):

    def __init__(self):
        super().__init__("cpu", psutil.cpu_count() or 1)

    def get_configuration(self):
        return {
            "name": self.name,
            "valueCount": self.valueCount,
            "extent": [0, 100],
        }

    # TODO cache, history (timestamp)
    def get_values(self):
        cpu_percent = psutil.cpu_percent(None, True)

        return cpu_percent


class SingleCpuProbe(Probe):

    def __init__(self):
        super().__init__("cpu-single")

    def get_configuration(self):
        return {
            "name": self.name,
            "valueCount": self.valueCount,
            "extent": [0, 100],
            "height": 4,
            "colors": ["#006d2c", "#31a354", "#74c476", "#bae4b3", "#bdd7e7", "#6baed6", "#3182bd", "#08519c"],
        }

    def get_values(self):
        cpu_percent = psutil.cpu_percent()

        return [cpu_percent]


class ArduinoSingleSensorProbe(Probe):

    def __init__(self, sensor, port=None, pspeed=None, extent=None):
        super().__init__(sensor)
        self.sensor = sensor
        self.port = port
        self.pspeed = pspeed
        self.extent = extent

    def get_configuration(self):
        return {
            "name": self.name,
            "valueCount": self.valueCount,
            "extent": self.extent if self.extent else [0, 255],
            "height": 4,
        }

    def get_values(self):
        value = get_value(self.port, self.pspeed, self.sensor)

        return [value]

probes.append(CpuProbe())
probes.append(SingleCpuProbe())
probes.append(ArduinoSingleSensorProbe("light"))
probes.append(ArduinoSingleSensorProbe("DHT_temp", extent=[15, 40]))
probes.append(ArduinoSingleSensorProbe("DHT_hum", extent=[10, 90]))


@asyncio.coroutine
def sysinfo():
    while True:
        response = { probe.name: probe.get_data() for probe in probes }

        json_response = simplejson.dumps({ "data": response })
        for ws in websockets:
            ws.send(json_response)
        yield from asyncio.sleep(1)


def configuration():
    return { probe.name: probe.get_configuration() for probe in probes }


def start_server(loop):
    # sysinfo
    asyncio.async(sysinfo())

    # websocket
    ws = loop.create_server(
        lambda: WebSocketProtocol(SysInfoWebSocket),
        '',
        9007
    )
    loop.run_until_complete(ws)
    print("WebSocket server started.")


class SysInfoWebSocket(WebSocket):

    def opened(self):
        websockets.append(self)
        self.send(simplejson.dumps({ "configuration": configuration() }))

    def closed(self, code, reason=None):
        websockets.remove(self)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    start_server(loop)

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        print("Closing loop.")
        loop.close()
