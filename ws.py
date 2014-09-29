#!/usr/bin/env python

import asyncio
import psutil
import simplejson
from ws4py.async_websocket import WebSocket
from ws4py.server.tulipserver import WebSocketProtocol

websockets = []

@asyncio.coroutine
def sysinfo():
    while True:
        cpu_percent = psutil.cpu_percent()
        response = {
            "cpu": cpu_percent
        }
        json_response = simplejson.dumps(response)
        for ws in websockets:
            ws.send(json_response)
        yield from asyncio.sleep(1)


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
