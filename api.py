import ipaddress, threading, socket, random, logging, string, secrets, json, time, os, re
from bottle import HTTPResponse, route, run, request, template
from logging.handlers import RotatingFileHandler
from Class.wireguard import Wireguard
from Class.templator import Templator
from threading import Thread
from pathlib import Path

tokens = []
connectMutex = threading.Lock()
updateMutex = threading.Lock()
folder = os.path.dirname(os.path.realpath(__file__))
#wireguard
wg = Wireguard(folder)
config = wg.getConfig()
#pull subnetPrefix
subnetPrefix = ".".join(config['subnet'].split(".")[:2])
#templator
templator = Templator()
#logging
level = "info"
levels = {'critical': logging.CRITICAL,'error': logging.ERROR,'warning': logging.WARNING,'info': logging.INFO,'debug': logging.DEBUG}
stream_handler = logging.StreamHandler()
stream_handler.setLevel(levels[level])
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',datefmt='%d.%m.%Y %H:%M:%S',level=levels[level],handlers=[RotatingFileHandler(maxBytes=10000000,backupCount=5,filename=f"{folder}/logs/api.log"),stream_handler])
#token
tokens = {"connect":[],"peer":[]}
for i in range(3):
    token =  phrase = ''.join(random.choices(string.ascii_uppercase + string.digits, k=18))
    logging.info(f"Adding connect token {token}")
    tokens['connect'].append(token)
for i in range(3):
    token =  phrase = ''.join(random.choices(string.ascii_uppercase + string.digits, k=18))
    logging.info(f"Adding peer token {token}")
    tokens['peer'].append(token)
try:
    wg.saveJson(tokens,f"{folder}/tokens.json")
except:
    logging.warning("Failed to write token file")

def validateToken(payload):
    if not "token" in payload: return False
    token = re.findall(r"^([A-Za-z0-9/.=+]{18,60})$",payload['token'],re.MULTILINE | re.DOTALL)
    if not token: return False
    if "network" in payload and payload["network"] == "Peer":
        if payload['token'] not in tokens['peer']: return False
    else:
        if payload['token'] not in tokens['connect']: return False
    return True

def validateID(id):
    result = re.findall(r"^[0-9]{1,4}$",str(id),re.MULTILINE | re.DOTALL)
    if not result: return False
    return True

def validatePort(port):
    result = re.findall(r"^[0-9]{4,5}$",str(port),re.MULTILINE | re.DOTALL)
    if not result: return False
    return True

def validateNetwork(network):
    result = re.findall(r"^[A-Za-z]{3,6}$",network,re.MULTILINE | re.DOTALL)
    if not result: return False
    return True

def validateLinkType(linkType):
    linkTypes = ["default","wgobfs","ipt_xor","amneziawg"]
    if linkType in linkTypes: return True
    return False

def validatePrefix(prefix):
    result = re.findall(r"^[0-9.]{4,6}$",prefix,re.MULTILINE | re.DOTALL)
    if not result: return False
    return True

def validateConnectivity(connectivity):
    if "ipv4" not in connectivity or "ipv6" not in connectivity: return False
    try:
        if connectivity['ipv4']:
            ip_obj = ipaddress.ip_address(connectivity['ipv4'])
        if connectivity['ipv6']:
            ip_obj = ipaddress.ip_address(connectivity['ipv6'])
    except ValueError:
        return False
    return True

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

def getInternal(requestIP):
    try:
        return ipaddress.ip_address(requestIP) in ipaddress.ip_network(config['subnet'])
    except:
        return False

@route('/connectivity',method='POST')
def index():
    requestIP = getReqIP()
    isInternal = getInternal(requestIP)
    payload = json.load(request.body)
    #validate token
    if not isInternal and not validateToken(payload): 
        logging.info(f"Invalid Token from {requestIP}")
        return HTTPResponse(status=401, body="Invalid Token")
    return HTTPResponse(status=200, body={'connectivity':config['connectivity'],'linkTypes':config['linkTypes'],'subnetPrefix':subnetPrefix})

@route('/connect', method='POST')
def index():
    requestIP = getReqIP()
    isInternal = getInternal(requestIP)
    payload = json.load(request.body)
    #validate token
    if not isInternal and not validateToken(payload): 
        logging.info(f"Invalid Token from {requestIP}")
        return HTTPResponse(status=401, body="Invalid Token")
    #validate id
    if not 'id' in payload or not validateID(payload['id']): 
        logging.info(f"Invalid ID from {requestIP}")
        return HTTPResponse(status=400, body="Invalid ID")
    #validate port
    if "port" in payload and not validatePort(payload['port']): 
        logging.info(f"Invalid Port from {requestIP}")
        return HTTPResponse(status=400, body="Invalid Port")
    #validate prefix
    if "prefix" in payload and not validatePrefix(payload['prefix']):
        logging.info(f"Invalid Prefix from {requestIP}")
        return HTTPResponse(status=400, body="Invalid Prefix")
    #validate network
    if "network" in payload and payload['network'] != "" and not validateNetwork(payload['network']):
        logging.info(f"Invalid Network from {requestIP}")
        return HTTPResponse(status=400, body="Invalid Network")
    #validate linkType
    if "linkType" in payload and not validateLinkType(payload['linkType']):
        logging.info(f"Invalid linkType from {requestIP}")
        return HTTPResponse(status=400, body="Invalid linkType")
    #validate area
    if "area" in payload and not validateID(payload['area']):
        logging.info(f"Invalid Area from {requestIP}")
        return HTTPResponse(status=400, body="Invalid Area")
    #validate connectivity
    if "connectivity" in payload and not validateConnectivity(payload['connectivity']):
        logging.info(f"Invalid connectivity data from {requestIP}")
        return HTTPResponse(status=400, body="Invalid connectivity data")
    #prevent local connects
    if payload['id'] == config['id']:
        logging.info(f"Invalid connection from {requestIP}")
        return HTTPResponse(status=400,body="Are you trying to connect to yourself?!")
    #defaults
    if not "connectivity" in payload: payload['connectivity'] = {"ipv4":"","ipv6":""}
    if not "linkType" in payload: payload['linkType'] = "default"
    if not "network" in payload: payload['network'] = ""
    if not "initial" in payload: payload['initial'] = False
    if not "prefix" in payload: payload['prefix'] = f"{subnetPrefix}"
    if not "area" in payload: payload['area'] = 0
    payload['basePort'] = config['basePort'] if not "port" in payload else payload['port']
    if not "ipv6" in payload: payload['ipv6'] = False
    #initial
    if payload['initial']:
        routes = wg.cmd("birdc show route")[0]
        subnetPrefixSplitted = payload['prefix'].split(".")
        targets = re.findall(f"({subnetPrefixSplitted[0]}\.{subnetPrefixSplitted[1]}\.[0-9]+\.0\/30)",routes, re.MULTILINE)
        if f"{payload['prefix']}.{payload['id']}.0/30" in targets: 
            logging.info(f"ID Collision from {requestIP}")
            return HTTPResponse(status=416, body="Collision")
    #generate interface name
    interfaceType = "v6" if payload['ipv6'] else ""
    interface = wg.getInterface(payload['id'],interfaceType,payload['network'])
    #check if interface exists
    if os.path.isfile(f"{folder}/links/{interface}.sh") or os.path.isfile(f"{folder}/links/{interface}Serv.sh"):
        return HTTPResponse(status=412, body="link already exists")
    #block any other requests to prevent issues regarding port and ip assignment
    connectMutex.acquire()
    #generate new key pair
    privateKeyServer, publicKeyServer = wg.genKeys()
    preSharedKey = wg.genPreShared()
    wgobfsSharedKey = secrets.token_urlsafe(24)
    #load configs
    configs = wg.getConfigs(False)
    lastbyte,port = wg.minimal(configs,4,payload['basePort'])
    #generate wireguard config
    serverConfig = templator.genServer(interface,config,payload,lastbyte,port,wgobfsSharedKey)
    #save
    logging.debug(f"Creating wireguard link {interface}")
    wg.saveFile(privateKeyServer,f"{folder}/links/{interface}.key")
    wg.saveFile(preSharedKey,f"{folder}/links/{interface}.pre")
    wg.saveFile(serverConfig,f"{folder}/links/{interface}.sh")
    remotePublic = payload['connectivity']['ipv6'] if "v6" in interface else payload['connectivity']['ipv4']
    linkConfig = {'remote':f"{payload['prefix']}.{config['id']}.1",'remotePublic':remotePublic.replace("[","").replace("]","")}
    wg.saveJson(linkConfig,f"{folder}/links/{interface}.json")
    logging.debug(f"{interface} up")
    wg.setInterface(interface,"up")
    #check for dummy
    if not "dummy" in configs:
        logging.debug(f"Creating dummy")
        dummyConfig = templator.genDummy(config,config['connectivity'])
        wg.saveFile(dummyConfig,f"{folder}/links/dummy.sh")
        logging.debug(f"dummy up")
        wg.setInterface("dummy","up")
    connectMutex.release()
    logging.info(f"{interface} created for {requestIP}")
    return HTTPResponse(status=200, body={"publicKeyServer":publicKeyServer,'preSharedKey':preSharedKey,'wgobfsSharedKey':wgobfsSharedKey,'id':config['id'],'lastbyte':lastbyte,'port':port,'connectivity':config['connectivity']})

@route('/update', method='PATCH')
def index():
    requestIP = getReqIP()
    payload = json.load(request.body)
    #validate interface name
    interface = re.findall(r"^[A-Za-z0-9]{3,50}$",payload['interface'], re.MULTILINE)
    if not interface: 
        logging.info(f"Invalid interface name from {requestIP}")
        return HTTPResponse(status=400, body="Invalid link name")
    #check if interface exists
    if not os.path.isfile(f"{folder}/links/{payload['interface']}.sh"):
        logging.info(f"Invalid link from {requestIP}")
        return HTTPResponse(status=400, body="invalid link")
    #read private key
    with open(f"{folder}/links/{payload['interface']}.key", 'r') as file: privateKeyServer = file.read()
    #get public key from private key
    publicKeyServer = wg.getPublic(privateKeyServer)
    #check if they match
    if payload['publicKeyServer'] != publicKeyServer:
        logging.info(f"Invalid public key from {requestIP}")
        return HTTPResponse(status=400, body="invalid public key")
    #update
    wg.setInterface(payload['interface'],"down")
    #since cost adjustments go through a pipe, there needs to be a mutex
    if "cost" in payload: updateMutex.acquire()
    logging.info(f"{payload['interface']} updating link")
    wg.updateLink(payload['interface'],payload)
    wg.setInterface(payload['interface'],"up")
    #the pipe is fetched every 100ms, make sure we wait until the data is fetched
    if "cost" in payload:
        time.sleep(0.1)
        updateMutex.release()
    return HTTPResponse(status=200, body="link updated")

@route('/disconnect', method='POST')
def index():
    requestIP = getReqIP()
    payload = json.load(request.body)
    #validate interface name
    interface = re.findall(r"^[A-Za-z0-9]{3,50}$",payload['interface'], re.MULTILINE)
    if not interface:
        logging.info(f"Invalid interface name from {requestIP}")
        return HTTPResponse(status=400, body="Invalid link name")
    #support older versions that are using Serv
    if os.path.isfile(f"{folder}/links/{payload['interface']}Serv.sh"): payload['interface'] = f"{payload['interface']}Serv"
    #check if interface exists
    if not os.path.isfile(f"{folder}/links/{payload['interface']}.sh"):
        logging.info(f"Invalid link from {requestIP}")
        return HTTPResponse(status=400, body="invalid link")
    #read private key
    with open(f"{folder}/links/{payload['interface']}.key", 'r') as file: privateKeyServer = file.read()
    #get public key from private key
    publicKeyServer = wg.getPublic(privateKeyServer)
    #check if they match
    if payload['publicKeyServer'] != publicKeyServer:
        logging.info(f"Invalid public key from {requestIP}")
        return HTTPResponse(status=400, body="invalid public key")
    #terminate the link
    if "wait" in payload and payload['wait'] == False:
        terminateLink(folder,payload['interface'],False)
        logging.info(f"{payload['interface']} terminated")
    else:
        termination = Thread(target=terminateLink, args=([folder,payload['interface']]))
        termination.start()
        logging.info(f"{payload['interface']} started termination thread")
    return HTTPResponse(status=200, body="link terminated")

listen = '::' if config['listen'] == "public" else f"{subnetPrefix}.{config['id']}.1"
run(host=listen, port=config['listenPort'], server='paste')