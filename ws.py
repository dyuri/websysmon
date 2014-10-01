#!/usr/bin/env python

import asyncio
import psutil
import simplejson
import datetime
from ws4py.async_websocket import WebSocket
from ws4py.server.tulipserver import WebSocketProtocol

websockets = []
probes = []


class Probe():

    def __init__(self, name, valueCount=1):
        self.name = name
        self.valueCount = valueCount

    def get_values(self):
        raise NotImplementedError()

    def get_configuration(self):
        raise NotImplementedError()


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
        ts = int(datetime.datetime.now().timestamp() * 1000)

        return {
            "values": cpu_percent,
            "timestamp": ts,
        }


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
        ts = int(datetime.datetime.now().timestamp() * 1000)

        return {
            "values": cpu_percent,
            "timestamp": ts,
        }


probes.append(CpuProbe())
probes.append(SingleCpuProbe())


@asyncio.coroutine
def sysinfo():
    while True:
        response = { probe.name: probe.get_values() for probe in probes }

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


loop = asyncio.get_event_loop()
start_server(loop)

try:
    loop.run_forever()
except KeyboardInterrupt:
    pass
finally:
    print("Closing loop.")
    loop.close()
