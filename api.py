#!/usr/bin/python3

from http.server import HTTPServer, SimpleHTTPRequestHandler
from Class.wireguard import Wireguard
from Class.templator import Templator
from functools import partial
from Class.bird import Bird
import ipaddress, socket, random, string, json, os, re
from pathlib import Path

class MyHandler(SimpleHTTPRequestHandler):

    def __init__(self, config, folder, tokens, *args, **kwargs):
        self.folder = folder
        self.templator = Templator()
        self.wg = Wireguard(folder)
        self.config = config
        self.tokens = tokens
        self.bird = Bird()
        # BaseHTTPRequestHandler calls do_GET **inside** __init__ !!!
        # So we have to call super().__init__ after setting attributes.
        super().__init__(*args, **kwargs)

    def response(self,httpCode,payload):
        self.send_response(httpCode)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(bytes(json.dumps(payload).encode()))

    def validateToken(self,payload):
        if not "token" in payload:
            self.response(400,{"error":"missing token"})
            return False
        token = re.findall(r"^([A-Za-z0-9/.=+]{3,50})$",payload['token'],re.MULTILINE | re.DOTALL)
        if not token:
            self.response(401,{"error":"invalid token"})
            return False
        if payload['token'] not in self.tokens:
            self.response(401,{"error":"invalid token"})
            return False
        return True

    def do_GET(self):
        parts = self.path.split('/')
        if parts[1] == "peers":
            configs = self.wg.getConfigs(False)
            configs = self.wg.loadConfigs(configs)
            endpoints = self.wg.getEndpoints(configs)
            self.response(200,endpoints)
        else:
            self.response(200,{"status":"ok"})

    def do_POST(self):
        length = int(self.headers['Content-Length'])
        if length > 200:
            self.response(414,{"error":"way to fucking long"})
            return
        if len(self.path) > 20:
            self.response(414,{"error":"way to fucking long"})
            return
        payload = self.rfile.read(length).decode("utf-8")
        parts = self.path.split('/')
        isInternal =  ipaddress.ip_address(self.client_address[0]) in ipaddress.ip_network('10.0.0.0/8')
        if parts[1] == "connect":
            payload = json.loads(payload)
            #validate token
            if not isInternal:
                result = self.validateToken(payload)
                if not result: return
            #generate new key pair
            clientPrivateKey, ClientPublicKey = self.wg.genKeys()
            #generate interface name
            interface = self.wg.getInterface(payload['id'])
            #generate wireguard config
            clientConfig = self.templator.genClient(interface,payload['id'],payload['ip'],self.client_address[0],payload['port'],payload['publicKeyServer'])
            #save
            self.wg.saveFile(clientPrivateKey,f"{self.folder}/links/{interface}.key")
            self.wg.saveFile(clientConfig,f"{self.folder}/links/{interface}.sh")
            self.wg.setInterface(interface,"up")
            #load configs
            configs = self.wg.getConfigs()
            #check for dummy
            if not self.wg.hasDummy(configs):
                dummyConfig = self.templator.genDummy(self.config['id'])
                self.wg.saveFile(dummyConfig,f"{self.folder}/links/dummy.sh")
                self.wg.setInterface("dummy","up")
            self.bird.bird()
            self.response(200,{"clientPublicKey":ClientPublicKey,'id':self.config['id']})
            return
        elif parts[1] == "disconnect":
            payload = json.loads(payload)
            #validate interface name
            interface = re.findall(r"^[A-Za-z0-9]{3,50}$",payload['interface'], re.MULTILINE)
            if not interface:
                self.response(400,{"error":"invalid link name"})
                return
            #check if interface exists
            if os.path.isfile(f"{self.folder}/links/{payload['interface']}.sh"):
                #read private key
                with open(f"{self.folder}/links/{payload['interface']}.key", 'r') as file: privateKeyServer = file.read()
                #get public key from private key
                publicKeyServer = self.wg.getPublic(privateKeyServer)
                #check if they match
                if payload['publicKeyServer'] == publicKeyServer:
                    #terminate the link
                    self.wg.setInterface(payload['interface'],"down")
                    self.wg.cleanInterface(payload['interface'])
                    self.response(200,{"success":"link terminated"})
                else:
                    self.response(400,{"error":"invalid public key"})
            else:
                self.response(400,{"error":"invalid link"})
        else:
            self.response(501,{"error":"not implemented"})

print("Loading config")
with open('configs/config.json') as f:
    config = json.load(f)

tokens = []
folder = os.path.dirname(os.path.realpath(__file__))
wg = Wireguard(folder)
token =  phrase = ''.join(random.choices(string.ascii_uppercase + string.digits, k=18))
print(f"Adding Token {token}")
try:
    wg.saveFile(f"{token}\n",f"{folder}/token")
except:
    print("Failed to write token file")
tokens.append(token)

MyHandler = partial(MyHandler, config, folder, tokens)
server = HTTPServer(('', 8080), MyHandler)
print("Ready")
try:
    server.serve_forever()
except KeyboardInterrupt:
    server.socket.close()
