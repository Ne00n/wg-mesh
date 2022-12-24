#!/usr/bin/python3

from http.server import HTTPServer, SimpleHTTPRequestHandler
from Class.wireguard import Wireguard
from Class.templator import Templator
from functools import partial
import socket, json, os, re
from pathlib import Path

class MyHandler(SimpleHTTPRequestHandler):

    def __init__(self, config, *args, **kwargs):
        self.folder = "/opt/wg-mesh/"
        self.templator = Templator()
        self.wg = Wireguard()
        self.config = config
        # BaseHTTPRequestHandler calls do_GET **inside** __init__ !!!
        # So we have to call super().__init__ after setting attributes.
        super().__init__(*args, **kwargs)

    def response(self,httpCode,payload):
        self.send_response(httpCode)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(bytes(json.dumps(payload).encode()))

    def loadFile(self,file):
        with open(file, 'r') as file: return file.read()

    def saveFile(self,file,data):
        with open(file, "w") as file: file.write(data)

    def do_POST(self):
        print("post")
        length = int(self.headers['Content-Length'])
        if length > 200:
            self.response(414,{"error":"way to fucking long"})
            return
        if len(self.path) > 200:
            self.response(414,{"error":"way to fucking long"})
            return
        payload = self.rfile.read(length).decode("utf-8")
        empty, type = self.path.split('/')
        if type == "connect":
            payload = json.loads(payload)
            clientPrivateKey, ClientPublicKey = self.wg.genKeys()
            clientConfig = self.templator.genClient(self.config['id'],payload['ip'],self.client_address[0],payload['port'],clientPrivateKey,payload['publicKeyServer'])
            self.response(200,{"clientPublicKey":ClientPublicKey,'id':self.config['id']})
            return

    #/connectivity
    def do_GET(self):
        print("get")
        if len(self.path) > 200:
            self.response(414,{"error":"way to fucking long"})
            return
        parts = self.path.split('/')
        del parts[0]
        if len(parts) != 1 and len(parts) != 5:
            self.response(400,{"error":"incomplete"})
            return
        if len(parts) == 1:
            empty, type = self.path.split('/')
        elif len(parts) == 5:
            empty, type, requestType, wgType, protocol, name  = self.path.split('/')
        if type == "connectivity":
            self.response(200,{"success":self.config['connectivity']})

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
