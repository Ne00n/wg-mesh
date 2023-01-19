#!/usr/bin/python3

from http.server import HTTPServer, SimpleHTTPRequestHandler
from Class.wireguard import Wireguard
from Class.templator import Templator
from functools import partial
import ipaddress, socket, random, string, json, os, re
from pathlib import Path

class MyHandler(SimpleHTTPRequestHandler):

    def __init__(self, config, folder, tokens, *args, **kwargs):
        self.folder = folder
        self.templator = Templator()
        self.wg = Wireguard(folder)
        self.config = config
        self.tokens = tokens
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
        payload = json.loads(payload)
        if parts[1] == "connect":
            #validate token
            if not isInternal:
                result = self.validateToken(payload)
                if not result: return
            #generate new key pair
            privateKeyServer, publicKeyServer = self.wg.genKeys()
            #load configs
            configs = self.wg.getConfigs(False)
            lastbyte,port = self.wg.minimal(configs)
            #generate interface name
            interface = self.wg.getInterface(payload['id'],"Serv")
            #generate wireguard config
            serverConfig = self.templator.genServer(interface,self.config['id'],lastbyte,port,payload['clientPublicKey'])
            #save
            self.wg.saveFile(privateKeyServer,f"{self.folder}/links/{interface}.key")
            self.wg.saveFile(serverConfig,f"{self.folder}/links/{interface}.sh")
            self.wg.setInterface(interface,"up")
            #check for dummy
            if not self.wg.hasDummy(configs):
                dummyConfig = self.templator.genDummy(self.config['id'])
                self.wg.saveFile(dummyConfig,f"{self.folder}/links/dummy.sh")
                self.wg.setInterface("dummy","up")
            self.response(200,{"publicKeyServer":publicKeyServer,'id':self.config['id'],'lastbyte':lastbyte,'port':port,'connectivity':self.config['connectivity']})
            return
        elif parts[1] == "disconnect":
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

MyHandler = partial(MyHandler, wg.getConfig(), folder, tokens)
server = HTTPServer(('', 8080), MyHandler)
print("Ready")
try:
    server.serve_forever()
except KeyboardInterrupt:
    server.socket.close()
