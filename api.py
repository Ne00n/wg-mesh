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

    def do_GET(self):
        self.response(200,{"status":"ok"})
        return

    def do_POST(self):
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
            interface = self.wg.getInterface(payload['id'])
            clientConfig = self.templator.genClient(interface,payload['id'],payload['ip'],self.client_address[0],payload['port'],payload['publicKeyServer'])
            self.wg.saveFile(clientPrivateKey,f"{self.folder}links/{interface}.key")
            self.wg.saveFile(clientConfig,f"{self.folder}links/{interface}.sh")
            self.wg.setInterface(interface,"up")
            self.response(200,{"clientPublicKey":ClientPublicKey,'id':self.config['id']})
            return
        elif type == "disconnect":
            payload = json.loads(payload)
            interface = re.findall(r"^[A-Za-z0-9]{3,50}$",payload['interface'], re.MULTILINE)
            if not interface:
                self.response(400,{"error":"invalid link name"})
                return
            if os.path.isfile(f"{self.folder}links/{payload['interface']}.sh"):
                with open(f"{self.folder}links/{payload['interface']}.key", 'r') as file:
                    privateKeyServer = file.read()
                publicKeyServer = self.wg.getPublic(privateKeyServer)
                if payload['publicKeyServer'] == publicKeyServer:
                    self.wg.setInterface(payload['interface'],"down")
                    self.wg.cleanInterface(payload['interface'])
                    self.response(200,{"success":"link terminated"})
                else:
                    self.response(400,{"error":"invalid public key"})
            else:
                self.response(400,{"error":"invalid link"})

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
