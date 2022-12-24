#!/usr/bin/python3

from http.server import HTTPServer, SimpleHTTPRequestHandler
from functools import partial
import socket, json, os, re
from pathlib import Path

class MyHandler(SimpleHTTPRequestHandler):
    dir = "/opt/wg-mesh/"

    def __init__(self, config, *args, **kwargs):
        self.config = config
        # BaseHTTPRequestHandler calls do_GET **inside** __init__ !!!
        # So we have to call super().__init__ after setting attributes.
        super().__init__(*args, **kwargs)

    def response(self,httpCode,key,msg):
        self.send_response(httpCode)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(bytes(json.dumps({key: msg}).encode()))

    def loadFile(self,file):
        with open(file, 'r') as file: return file.read()

    def saveFile(self,file,data):
        with open(file, "w") as file: file.write(data)

    #/connectivity
    #/wireguard/request/server|client/v4|v6/name
    #/wireguard/delete/....
    def do_GET(self):
        if len(self.path) > 200:
            self.response(414,"error","way to fucking long")
            return
        parts = self.path.split('/')
        del parts[0]
        if len(parts) != 1 and len(parts) != 5:
            self.response(400,"error","incomplete")
            return
        if len(parts) == 1:
            empty, type = self.path.split('/')
        elif len(parts) == 5:
            empty, type, requestType, wgType, protocol, name  = self.path.split('/')
        if type == "connectivity":
            self.response(200,"success",self.config['connectivity'])
        elif type == "wireguard":
            self.response(200,"success","soon")

print("Loading config")
with open('configs/config.json') as f:
    config = json.load(f)

MyHandler = partial(MyHandler, config)
server = HTTPServer(('', 8080), MyHandler)
print("Ready")
try:
    server.serve_forever()
except KeyboardInterrupt:
    server.socket.close()
