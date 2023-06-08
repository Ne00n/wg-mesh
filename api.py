import ipaddress, threading, socket, random, logging, string, json, time, os, re
from bottle import HTTPResponse, route, run, request, template
from logging.handlers import RotatingFileHandler
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
#logging
level = "info"
levels = {'critical': logging.CRITICAL,'error': logging.ERROR,'warning': logging.WARNING,'info': logging.INFO,'debug': logging.DEBUG}
stream_handler = logging.StreamHandler()
stream_handler.setLevel(levels[level])
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',datefmt='%H:%M:%S',level=levels[level],handlers=[RotatingFileHandler(maxBytes=10000000,backupCount=5,filename=f"{folder}/logs/api.log"),stream_handler])
#token
token =  phrase = ''.join(random.choices(string.ascii_uppercase + string.digits, k=18))
logging.info(f"Adding Token {token}")
try:
    wg.saveFile(f"{token}\n",f"{folder}/token")
except:
    logging.warning("Failed to write token file")
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

def validatePort(port):
    result = re.findall(r"^[0-9]{4,5}$",port,re.MULTILINE | re.DOTALL)
    if not result: return False
    return True

def validateNetwork(network):
    result = re.findall(r"^[A-Za-z]{3,6}$",network,re.MULTILINE | re.DOTALL)
    if not result: return False
    return True

def validatePrefix(prefix):
    if prefix == "10.0." or prefix == "172.16.": return True
    return False

def terminateLink(folder,interface,wait=True):
    wg = Wireguard(folder)
    if wait: time.sleep(2)
    wg.setInterface(interface,"down")
    wg.cleanInterface(interface)
    return

def getReqIP():
    reqIP = request.environ.get('HTTP_X_REAL_IP') or request.environ.get('REMOTE_ADDR')
    logging.debug(f"{reqIP} connecting")
    if ipaddress.ip_address(reqIP).version == 6 and ipaddress.IPv6Address(reqIP).ipv4_mapped: return ipaddress.IPv6Address(reqIP).ipv4_mapped
    return reqIP

@route('/connectivity',method='POST')
def index():
    requestIP = getReqIP()
    isInternal =  ipaddress.ip_address(requestIP) in ipaddress.ip_network('10.0.0.0/8')
    payload = json.load(request.body)
    #validate token
    if not isInternal and not validateToken(payload): 
        logging.info(f"Invalid Token from {requestIP}")
        return HTTPResponse(status=401, body="Invalid Token")
    return HTTPResponse(status=200, body={'connectivity':config['connectivity']})

@route('/connect', method='POST')
def index():
    requestIP = getReqIP()
    isInternal =  ipaddress.ip_address(requestIP) in ipaddress.ip_network('10.0.0.0/8')
    payload = json.load(request.body)
    #validate token
    if not isInternal and not validateToken(payload): 
        logging.info(f"Invalid Token from {requestIP}")
        return HTTPResponse(status=401, body="Invalid Token")
    #validate id
    if not validateID(payload['id']): 
        logging.info(f"Invalid ID from {requestIP}")
        return HTTPResponse(status=404, body="Invalid ID")
    #validate port
    if "port" in payload and not validatePort(payload['port']): 
        logging.info(f"Invalid Port from {requestIP}")
        return HTTPResponse(status=404, body="Invalid Port")
    #validate prefix
    if "prefix" in payload and not validatePrefix(payload['prefix']):
        logging.info(f"Invalid Prefix from {requestIP}")
        return HTTPResponse(status=404, body="Invalid Prefix")
    #validate network
    if "network" in payload and not validateNetwork(payload['network']):
        logging.info(f"Invalid Network from {requestIP}")
        return HTTPResponse(status=404, body="Invalid Network")
    #defaults
    if not "network" in payload: payload['network'] = ""
    if not "initial" in payload: payload['initial'] = False
    if not "prefix" in payload: payload['prefix'] = "10.0."
    if not "port" in payload: payload['port'] = config['basePort']
    if not "ipv6" in payload: payload['ipv6'] = False
    #initial
    if payload['initial']:
        routes = wg.cmd("birdc show route")[0]
        targets = re.findall(f"(10\.0\.[0-9]+\.0\/30)",routes, re.MULTILINE)
        if f"10.0.{payload['id']}.0/30" in targets: 
            logging.info(f"ID Collision from {requestIP}")
            return HTTPResponse(status=416, body="Collision")
    #generate interface name
    servName = "v6Serv" if payload['ipv6'] else "Serv"
    interface = wg.getInterface(payload['id'],servName,payload['network'])
    #check if interface exists
    if os.path.isfile(f"{folder}/links/{interface}.sh"):
        return HTTPResponse(status=412, body="link already exists")
    #block any other requests to prevent issues regarding port and ip assignment
    mutex.acquire()
    #generate new key pair
    privateKeyServer, publicKeyServer = wg.genKeys()
    #load configs
    configs = wg.getConfigs(False)
    lastbyte,port = wg.minimal(configs,4,payload['basePort'])
    #generate wireguard config
    serverConfig = templator.genServer(interface,config['id'],lastbyte,port,payload['clientPublicKey'],payload['prefix'])
    #save
    logging.debug(f"Creating wireguard link {interface}")
    wg.saveFile(privateKeyServer,f"{folder}/links/{interface}.key")
    wg.saveFile(serverConfig,f"{folder}/links/{interface}.sh")
    logging.debug(f"{interface} up")
    wg.setInterface(interface,"up")
    #check for dummy
    if not "dummy" in configs:
        logging.debug(f"Creating dummy")
        dummyConfig = templator.genDummy(config['id'],config['connectivity'])
        wg.saveFile(dummyConfig,f"{folder}/links/dummy.sh")
        logging.debug(f"dummy up")
        wg.setInterface("dummy","up")
    mutex.release()
    logging.info(f"{interface} created for {requestIP}")
    return HTTPResponse(status=200, body={"publicKeyServer":publicKeyServer,'id':config['id'],'lastbyte':lastbyte,'port':port,'connectivity':config['connectivity']})

@route('/update', method='PATCH')
def index():
    reqIP = request.environ.get('HTTP_X_REAL_IP') or request.environ.get('REMOTE_ADDR')
    logging.debug(f"{reqIP} connecting")
    payload = json.load(request.body)
    #validate interface name
    interface = re.findall(r"^[A-Za-z0-9]{3,50}$",payload['interface'], re.MULTILINE)
    if not interface: 
        logging.info(f"Invalid interface name from {reqIP}")
        return HTTPResponse(status=400, body="Invalid link name")
    #check if interface exists
    if not os.path.isfile(f"{folder}/links/{payload['interface']}.sh"):
        logging.info(f"Invalid link from {reqIP}")
        return HTTPResponse(status=400, body="invalid link")
    #read private key
    with open(f"{folder}/links/{payload['interface']}.key", 'r') as file: privateKeyServer = file.read()
    #get public key from private key
    publicKeyServer = wg.getPublic(privateKeyServer)
    #check if they match
    if payload['publicKeyServer'] != publicKeyServer:
        logging.info(f"Invalid public key from {reqIP}")
        return HTTPResponse(status=400, body="invalid public key")
    #update
    wg.setInterface(interface,"down")
    wg.updateServer(interface,payload)
    wg.setInterface(interface,"up")
    return HTTPResponse(status=200, body="link updated")

@route('/disconnect', method='POST')
def index():
    reqIP = request.environ.get('HTTP_X_REAL_IP') or request.environ.get('REMOTE_ADDR')
    logging.debug(f"{reqIP} connecting")
    payload = json.load(request.body)
    #validate interface name
    interface = re.findall(r"^[A-Za-z0-9]{3,50}$",payload['interface'], re.MULTILINE)
    if not interface: 
        logging.info(f"Invalid interface name from {reqIP}")
        return HTTPResponse(status=400, body="Invalid link name")
    #check if interface exists
    if not os.path.isfile(f"{folder}/links/{payload['interface']}.sh"):
        logging.info(f"Invalid link from {reqIP}")
        return HTTPResponse(status=400, body="invalid link")
    #read private key
    with open(f"{folder}/links/{payload['interface']}.key", 'r') as file: privateKeyServer = file.read()
    #get public key from private key
    publicKeyServer = wg.getPublic(privateKeyServer)
    #check if they match
    if payload['publicKeyServer'] != publicKeyServer:
        logging.info(f"Invalid public key from {reqIP}")
        return HTTPResponse(status=400, body="invalid public key")
    #terminate the link
    logging.debug(f"starting termination thread")
    if "wait" in payload and payload['wait'] == False:
        terminateLink(folder,payload['interface'],False)
    else:
        termination = Thread(target=terminateLink, args=([folder,payload['interface']]))
        termination.start()
    logging.info(f"{payload['interface']} terminated")
    return HTTPResponse(status=200, body="link terminated")

listen = '::' if config['listen'] == "public" else f"10.0.{config['id']}.1"
run(host=listen, port=8080, server='paste')