import ipaddress, threading, socket, logging, string, secrets, json, time, os, re
from bottle import HTTPResponse, route, run, request, template
from logging.handlers import RotatingFileHandler
from Class.wireguard import Wireguard
from Class.templator import Templator
from Class.validate import Validate
from threading import Thread
from random import randint
from pathlib import Path

connectMutex = threading.Lock()
updateMutex = threading.Lock()
folder = os.path.dirname(os.path.realpath(__file__))
#wireguard
wg = Wireguard(folder)
config = wg.getConfig()
#validation
validate = Validate()
#pull subnetPrefix
subnetPrefix = ".".join(config['subnet'].split(".")[:2])
#templator
templator = Templator()
#logging
level = config['loglevel']
levels = {'critical': logging.CRITICAL,'error': logging.ERROR,'warning': logging.WARNING,'info': logging.INFO,'debug': logging.DEBUG}
stream_handler = logging.StreamHandler()
stream_handler.setLevel(levels[level])
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',datefmt='%d.%m.%Y %H:%M:%S',level=levels[level],handlers=[RotatingFileHandler(maxBytes=10000000,backupCount=5,filename=f"{folder}/logs/api.log"),stream_handler])
blocklist = {}
#token
tokens = {"connect":[],"peer":[]}
for i in range(3):
    token =  phrase = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(18))
    logging.info(f"Adding connect token {token}")
    tokens['connect'].append(token)
for i in range(3):
    token =  phrase = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(18))
    logging.info(f"Adding peer token {token}")
    tokens['peer'].append(token)
try:
    wg.saveFile(tokens,f"{folder}/tokens.json")
except:
    logging.warning("Failed to write token file")

def block(requestIP,check=False):
    if check and requestIP not in blocklist:
        return False
    elif not requestIP in blocklist:
        blocklist[requestIP] = int(time.time()) + randint(120,300)
    elif time.time() > blocklist[requestIP]:
        del blocklist[requestIP]
    else:
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

def check(requestIP,request):
    if block(requestIP,check=True): 
        logging.info(f"{requestIP} in blocklist")
        return 403,"IP blocked"
    if len(request.content_length) > 1000: 
        logging.info(f"{requestIP} payload is to large")
        return 413,"Payload to large"
    return None,None

@route('/connectivity',method='POST')
def index():
    requestIP = getReqIP()
    isInternal = getInternal(requestIP)
    status, body = check(requestIP,request)
    if status: return HTTPResponse(status=status, body=body)
    #validate token
    if not isInternal and not validate.token(payload,tokens): 
        logging.info(f"Invalid Token from {requestIP}")
        block(requestIP)
        return HTTPResponse(status=401, body="Invalid Token")
    geo = config['geo'] if "geo" in config else {}
    return HTTPResponse(status=200, body={'connectivity':config['connectivity'],'geo':geo,'linkTypes':config['linkTypes'],'subnetPrefix':subnetPrefix})

@route('/neighbour',method='POST')
def index():
    #is available
    if not config['modules']['neighbour']:
        return HTTPResponse(status=400, body="Bad Request")
    #grab IP
    requestIP = getReqIP()
    isInternal = getInternal(requestIP)
    status, body = check(requestIP,request)
    if status: return HTTPResponse(status=status, body=body)
    payload = json.load(request.body)
    #validate token
    if not isInternal and not validate.token(payload,tokens): 
        logging.info(f"Invalid Token from {requestIP}")
        block(requestIP)
        return HTTPResponse(status=401, body="Invalid Token")
    neighbours = wg.getNeighbours()
    return HTTPResponse(status=200, body=neighbours)

@route('/connect', method='POST')
def index():
    requestIP = getReqIP()
    isInternal = getInternal(requestIP)
    status, body = check(requestIP,request)
    if status: return HTTPResponse(status=status, body=body)
    payload = json.load(request.body)
    #validate token
    if not isInternal and not validate.token(payload,tokens): 
        logging.info(f"Invalid Token from {requestIP}")
        block(requestIP)
        return HTTPResponse(status=401, body="Invalid Token")
    #validate id
    if not 'id' in payload or not validate.id(payload['id']): 
        logging.info(f"Invalid ID from {requestIP}")
        return HTTPResponse(status=400, body="Invalid ID")
    #validate port
    if "port" in payload and not validate.port(payload['port']): 
        logging.info(f"Invalid Port from {requestIP}")
        return HTTPResponse(status=400, body="Invalid Port")
    #validate prefix
    if "prefix" in payload and not validate.prefix(payload['prefix']):
        logging.info(f"Invalid Prefix from {requestIP}")
        return HTTPResponse(status=400, body="Invalid Prefix")
    #validate network
    if "network" in payload and payload['network'] != "" and not validate.network(payload['network']):
        logging.info(f"Invalid Network from {requestIP}")
        return HTTPResponse(status=400, body="Invalid Network")
    #validate linkType
    if "linkType" in payload and not validate.linkType(payload['linkType'],config):
        logging.info(f"Invalid linkType from {requestIP}")
        return HTTPResponse(status=400, body="Invalid linkType")
    #validate connectivity
    if "connectivity" in payload and not validateConnectivity(payload['connectivity']):
        logging.info(f"Invalid connectivity data from {requestIP}")
        return HTTPResponse(status=400, body="Invalid connectivity data")
    #validate protocol
    if not "protocol" in payload and not validate.protocol(payload['protocol']):
        logging.info(f"Invalid protocol from {requestIP}")
        return HTTPResponse(status=400, body="Invalid protocol")
    #prevent local connects
    if payload['id'] == config['id']:
        logging.info(f"Invalid connection from {requestIP}")
        return HTTPResponse(status=400,body="Invalid Origin")
    #defaults
    if not "connectivity" in payload: payload['connectivity'] = {"ipv4":"","ipv6":""}
    if not "linkType" in payload: payload['linkType'] = "default"
    if not "network" in payload: payload['network'] = ""
    if not "initial" in payload: payload['initial'] = False
    if not "prefix" in payload: payload['prefix'] = f"{subnetPrefix}"
    payload['basePort'] = config['basePort'] if not "port" in payload else payload['port']
    #initial
    if payload['initial']:
        routes = wg.cmd("birdc show route")[0]
        subnetPrefixSplitted = payload['prefix'].split(".")
        targets = re.findall(f"({subnetPrefixSplitted[0]}\.{subnetPrefixSplitted[1]}\.[0-9]+\.0\/30)",routes, re.MULTILINE)
        if f"{payload['prefix']}.{payload['id']}.0/30" in targets or (payload['prefix'] == "10.0" and f"{payload['prefix']}.{int(payload['id'])+1}.0/30" in targets): 
            logging.info(f"ID Collision from {requestIP}")
            return HTTPResponse(status=416, body="Collision")
    #generate interface name
    interfaceType = "v6" if payload['protocol'] == "ipv6" else ""
    interface = wg.getInterface(payload['id'],interfaceType,payload['network'])
    #check if interface exists
    if os.path.isfile(f"{folder}/links/{interface}.sh"):
        logging.info(f"Link already exists, {requestIP}")
        return HTTPResponse(status=412, body="Link already exists")
    #connectivity blacklist check
    if "connectivity" in payload and "blacklist" in payload['connectivity'] and "geo" in config and "countryCode" in config['geo']:
        if config['geo']['countryCode'] in payload['connectivity']['blacklist']:
            return HTTPResponse(status=451,body="Country blacklisted")
    #block any other requests to prevent issues regarding port and ip assignment
    connectMutex.acquire()
    #generate new key pair
    privateKeyServer, publicKeyServer = wg.genKeys()
    preSharedKey = wg.genPreShared()
    wgobfsSharedKey = secrets.token_urlsafe(24)
    #switch to peer subnet if required
    isPeer = True if payload['network'] == "peer" else False
    #load configs
    configs = wg.getConfigs(False)
    freeSubnet,freeSubnetv6,freePort = wg.minimal(configs,payload['basePort'],isPeer)
    if not freeSubnet or not freeSubnetv6:
        connectMutex.release()
        logging.info(f"Unable to allocate subnet for {requestIP}")
        return HTTPResponse(status=500, body="Unable to allocate subnet.")
    #amneziawg
    amneziaConfig = wg.genAmneziaConfig()
    #check if amnezia is requested but also if we are using vanilla amnezia or with modded config
    if payload['linkType'] == "amneziawg" and config['linkSettings']['awgGen'] and amneziaConfig:
        payload["amneziawg"] = amneziaConfig
        configAsString = ''.join(f"{k}:{v}," for k, v in amneziaConfig.items())
        logging.info(f"Used config for amneziawg: {configAsString}")
    #generate wireguard config
    serverConfig = templator.genServer(interface,config,payload,freeSubnet,freeSubnetv6,freePort,wgobfsSharedKey)
    #save
    logging.debug(f"Creating wireguard link {interface}")
    wg.saveFile(privateKeyServer,f"{folder}/links/{interface}.key")
    wg.saveFile(preSharedKey,f"{folder}/links/{interface}.pre")
    wg.saveFile(serverConfig,f"{folder}/links/{interface}.sh")
    remotePublic = payload['connectivity']['ipv6'] if "v6" in interface else payload['connectivity']['ipv4']
    linkConfig = {'remote':f"{payload['prefix']}.{payload['id']}.1",'remotePublic':remotePublic.replace("[","").replace("]",""),"linkType":payload['linkType'],"mtu":1412}
    wg.saveFile(linkConfig,f"{folder}/links/{interface}.json")
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
    response = {"publicKeyServer":publicKeyServer,'preSharedKey':preSharedKey,'wgobfsSharedKey':wgobfsSharedKey,'id':config['id'],'networkID':config['networkID']
    ,'freeSubnet':wg.Network.getHost(freeSubnet),"freeSubnetv6":wg.Network.getHost(freeSubnetv6,"127"),'freePort':freePort,'connectivity':config['connectivity']}
    #append config if amneziawg
    if payload['linkType'] == "amneziawg" and config['linkSettings']['awgGen']: response["amneziawg"] = payload['amneziawg']
    return HTTPResponse(status=200, body=response)

@route('/update', method='PATCH')
def index():
    #is available
    if not config['modules']['update']:
        return HTTPResponse(status=400, body="Bad Request")
    #grab IP
    requestIP = getReqIP()
    status, body = check(requestIP,request)
    if status: return HTTPResponse(status=status, body=body)
    payload = json.load(request.body)
    #validate interface name
    interface = re.findall(r"^[A-Za-z0-9]{3,50}$",payload['interface'], re.MULTILINE)
    if not interface: 
        logging.info(f"Invalid interface name from {requestIP}")
        return HTTPResponse(status=400, body="Invalid link name")
    #check if interface exists
    if not os.path.isfile(f"{folder}/links/{payload['interface']}.sh"):
        logging.info(f"Invalid link from {requestIP}")
        block(requestIP)
        return HTTPResponse(status=400, body="invalid link")
    #read private key
    with open(f"{folder}/links/{payload['interface']}.key", 'r') as file: privateKeyServer = file.read()
    #get public key from private key
    publicKeyServer = wg.getPublic(privateKeyServer)
    #check if they match
    if payload['publicKeyServer'] != publicKeyServer:
        logging.info(f"Invalid public key from {requestIP}")
        block(requestIP)
        return HTTPResponse(status=400, body="invalid public key")
    #always apply the mutex
    updateMutex.acquire()
    #update
    wg.setInterface(payload['interface'],"down")
    logging.info(f"{payload['interface']} updating link")
    wg.updateLink(payload['interface'],payload)
    wg.setInterface(payload['interface'],"up")
    #the pipe is fetched every 100ms, make sure we wait until the data is fetched
    if "cost" in payload: time.sleep(0.1)
    updateMutex.release()
    return HTTPResponse(status=200, body="link updated")

@route('/disconnect', method='POST')
def index():
    requestIP = getReqIP()
    status, body = check(requestIP,request)
    if status: return HTTPResponse(status=status, body=body)
    payload = json.load(request.body)
    #validate interface name
    interface = re.findall(r"^[A-Za-z0-9]{3,50}$",payload['interface'], re.MULTILINE)
    if not interface:
        logging.info(f"Invalid interface name from {requestIP}")
        return HTTPResponse(status=400, body="Invalid link name")
    #block any other requests to prevent issues regarding port and ip assignment
    connectMutex.acquire()
    #check if interface exists
    if not os.path.isfile(f"{folder}/links/{payload['interface']}.sh"):
        logging.info(f"Invalid link from {requestIP}")
        block(requestIP)
        connectMutex.release()
        return HTTPResponse(status=400, body="invalid link")
    #read private key
    with open(f"{folder}/links/{payload['interface']}.key", 'r') as file: privateKeyServer = file.read()
    #get public key from private key
    publicKeyServer = wg.getPublic(privateKeyServer)
    #check if they match
    if payload['publicKeyServer'] != publicKeyServer:
        logging.info(f"Invalid public key from {requestIP}")
        block(requestIP)
        connectMutex.release()
        return HTTPResponse(status=400, body="invalid public key")
    #terminate the link
    if "wait" in payload and payload['wait'] == False:
        terminateLink(folder,payload['interface'],False)
        logging.info(f"{payload['interface']} terminated")
    else:
        termination = Thread(target=terminateLink, args=([folder,payload['interface']]))
        termination.start()
        logging.info(f"{payload['interface']} started termination thread")
    connectMutex.release()
    return HTTPResponse(status=200, body="link terminated")

listen = '::' if config['listen'] == "public" else f"{subnetPrefix}.{config['id']}.1"
run(host=listen, port=config['listenPort'], server='paste')