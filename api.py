import ipaddress, threading, socket, random, string, json, time, os, re
from bottle import HTTPResponse, route, run, request, template
from Class.wireguard import Wireguard
from Class.templator import Templator
from threading import Thread
from pathlib import Path

tokens = []
mutex = threading.Lock()
folder = os.path.dirname(os.path.realpath(__file__))
#wireguard
wg = Wireguard(folder)
config = wg.getConfig()
#templator
templator = Templator()
#token
token =  phrase = ''.join(random.choices(string.ascii_uppercase + string.digits, k=18))
print(f"Adding Token {token}")
try:
    wg.saveFile(f"{token}\n",f"{folder}/token")
except:
    print("Failed to write token file")
tokens.append(token)

def validateToken(payload):
    if not "token" in payload: return False
    token = re.findall(r"^([A-Za-z0-9/.=+]{18,60})$",payload['token'],re.MULTILINE | re.DOTALL)
    if not token: return False
    if payload['token'] not in tokens: return False
    return True

def validateID(id):
    result = re.findall(r"^[0-9]{1,4}$",id,re.MULTILINE | re.DOTALL)
    if not result: return False
    return True

def terminateLink(folder,interface):
    wg = Wireguard(folder)
    time.sleep(2)
    wg.setInterface(interface,"down")
    wg.cleanInterface(interface)
    return

@route('/connect', method='POST')
def index():
    reqIP = request.environ.get('REMOTE_ADDR')
    ip = ipaddress.ip_address(reqIP)
    if ip.version == 4:
        requestIP = reqIP
    elif ip.version == 6 and ipaddress.IPv6Address(reqIP).ipv4_mapped:
        requestIP = ipaddress.IPv6Address(reqIP).ipv4_mapped
    else:
        requestIP = reqIP
    isInternal =  ipaddress.ip_address(requestIP) in ipaddress.ip_network('10.0.0.0/8')
    payload = json.load(request.body)
    #validate token
    if not isInternal:
        if not validateToken(payload): return HTTPResponse(status=401, body="Invalid Token")
    #validate id
    if not validateID(payload['id']): return HTTPResponse(status=404, body="Invalid ID")
    #block any other requests to prevent issues regarding port and ip assignment
    mutex.acquire()
    #generate new key pair
    privateKeyServer, publicKeyServer = wg.genKeys()
    #load configs
    configs = wg.getConfigs(False)
    lastbyte,port = wg.minimal(configs)
    #generate interface name
    servName = "v6Serv" if payload['ipv6'] else "Serv"
    interface = wg.getInterface(payload['id'],servName)
    #generate wireguard config
    serverConfig = templator.genServer(interface,requestIP,config['id'],lastbyte,port,payload['clientPublicKey'])
    #save
    wg.saveFile(privateKeyServer,f"{folder}/links/{interface}.key")
    wg.saveFile(serverConfig,f"{folder}/links/{interface}.sh")
    wg.setInterface(interface,"up")
    #check for dummy
    if not "dummy" in configs:
        dummyConfig = templator.genDummy(config['id'])
        wg.saveFile(dummyConfig,f"{folder}/links/dummy.sh")
        wg.setInterface("dummy","up")
    mutex.release()
    return HTTPResponse(status=200, body={"publicKeyServer":publicKeyServer,'id':config['id'],'lastbyte':lastbyte,'port':port,'connectivity':config['connectivity']})

@route('/disconnect', method='POST')
def index():
    payload = json.load(request.body)
    #validate interface name
    interface = re.findall(r"^[A-Za-z0-9]{3,50}$",payload['interface'], re.MULTILINE)
    if not interface: return HTTPResponse(status=400, body="Invalid link name")
    #check if interface exists
    if os.path.isfile(f"{folder}/links/{payload['interface']}.sh"):
        #read private key
        with open(f"{folder}/links/{payload['interface']}.key", 'r') as file: privateKeyServer = file.read()
        #get public key from private key
        publicKeyServer = wg.getPublic(privateKeyServer)
        #check if they match
        if payload['publicKeyServer'] == publicKeyServer:
            #terminate the link
            termination = Thread(target=terminateLink, args=([folder,payload['interface']]))
            termination.start()
            return HTTPResponse(status=200, body="link terminated")
        else:
            return HTTPResponse(status=400, body="invalid public key")
    else:
        return HTTPResponse(status=400, body="invalid link")

listen = '::' if config['listen'] == "public" else f"10.0.{config['id']}.1"
run(host=listen, port=8080, server='paste')