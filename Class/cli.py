from logging.handlers import RotatingFileHandler
from Class.wireguard import Wireguard
from Class.templator import Templator
from Class.base import Base
from Class.bird import Bird
import subprocess, logging, random, time, sys, os, re

class CLI(Base):

    def __init__(self,path):
        self.path = path
        self.templator = Templator()
        self.wg = Wireguard(path,True)

    def init(self,id,listen):
        self.wg.init(id,listen)

    def used(self):
        self.wg = Wireguard(self.path)
        self.wg.used()

    def bender(self):
        self.wg = Wireguard(self.path)
        self.wg.bender()

    def connect(self,dest,token,linkType="default",port=51820,network=""):
        self.wg = Wireguard(self.path)
        config = self.wg.getConfig()
        if dest.startswith("pipe"):
            pipeTarget = re.findall(f"^{config['prefix']}([0-9]+)",dest, re.MULTILINE)
            if not pipeTarget: exit("Failed to parse pipe")
            subnetPrefix = ".".join(config['subnet'].split(".")[:2])
            dest = f"http://{subnetPrefix}.{pipeTarget[0]}.1:{config['listenPort']}"
        if linkType == "awg": linkType == "amneziawg"
        status = self.wg.connect(dest,token,linkType,port,network)
        if self.wg.getInitial():
            if not status['ipv4']['status'] and not status['ipv6']['status']:
                print(f"Initial link wasn't setup.")
                return 
            print("Waiting for meshing to complete.")
            for i in range(1, 300):
                if os.path.isfile(f"{self.path}/configs/state.json"): return
                time.sleep(1)
            print("Meshing seems to have failed.")

    def tunnel(self,task,tunnel=None):
        self.wg = Wireguard(self.path)
        config = self.wg.getConfig()
        if task == "create":
            tunnelID = None
            for run in range(1,10):
                tunnelID = random.randint(1, 250)
                if not os.path.isfile(f"{self.path}/links/tunnel{tunnelID}.sh"): break
                tunnelID = None
            if not tunnelID: exit("Unable to allocate tunnelID")
            print(f"Creating new tunnel{tunnelID}")
            #generate new client key pair
            clientPrivateKey, clientPublicKey = self.wg.genKeys()
            #generate new server key pair
            privateKeyServer, publicKeyServer = self.wg.genKeys()
            #generate new preshared secret
            preSharedKey = self.wg.genPreShared()
            #load existing tunnels / pipes
            allConfigs = self.wg.getConfigs(abort=False)
            #grab an available subnet + port
            freeSubnet,freeSubnetv6,freePort = self.wg.minimal(files=allConfigs,port=config['basePort'])
            #generate wireguard server config
            fakePayload = {'clientPublicKey':clientPublicKey,'linkType':'','prefix':'tunnel','connectivity':{"ipv4":True}}
            interface = self.wg.getInterface(id=tunnelID,prefix="tunnel")
            serverConfig = self.templator.genServer(interface,config,fakePayload,freeSubnet,freeSubnetv6,freePort)
            clientIP = self.wg.Network.getHost(freeSubnet)
            serverIP = freeSubnet.split("/")[0]
            clientIPv6 = self.wg.Network.getHost(freeSubnetv6,"127")
            clientConfig = self.templator.genExternalClient(config,serverIP,clientIP,clientIPv6,clientPrivateKey,publicKeyServer,preSharedKey,freePort)
            #save interface
            if os.path.isfile(f"{self.path}/links/{interface}.sh"): exit(f"{interface} already exists.")
            linkConfig = {'remote':f"{self.wg.Network.getSubnetPrefix()}.{config['id']}.1",'remotePublic':config['connectivity']['ipv4'],"linkType":"default"}
            self.wg.createInterface(interface,privateKeyServer,preSharedKey,serverConfig,linkConfig)
            #starting interface
            self.wg.setInterface(interface,"up")
            print("Wireguard client config")
            print(clientConfig)
        elif task == "delete":
            if tunnel is None: exit("You have to provide a tunnel")
            if not "tunnel" in tunnel: exit(f"{tunnel} invalid name")
            if not os.path.isfile(f"{self.path}/links/{tunnel}.sh"): exit(f"{tunnel} doesn't exists.")
            print(f"Deleting {tunnel}")
            self.wg.removeInterface(tunnel)

    def proximity(self,cutoff=0):
        self.wg = Wireguard(self.path)
        self.wg.proximity(cutoff)

    def reconnect(self,upgrade=False):
        self.wg = Wireguard(self.path)
        self.wg.reconnect(upgrade)

    def disconnect(self,links=[],force=False):
        self.wg = Wireguard(self.path)
        self.wg.disconnect(links,force)

    def links(self,state):
        files = os.listdir(f'{self.path}/links/')
        for file in list(files):
            if not file.endswith(".sh"): files.remove(file)
        for file in files:
            subprocess.run(f"bash {self.path}/links/{file} {state}",shell=True)

    def update(self):
        subprocess.run("cd; git pull",shell=True)

    def clean(self,ignoreEndpoint):
        self.wg = Wireguard(self.path)
        self.wg.clean(ignoreEndpoint)

    def migrate(self):
        self.wg = Wireguard(self.path,False,True)
        self.wg.updateConfig()

    def geo(self):
        config = self.readJson(f"{self.path}/configs/config.json")
        if not config:
            print("Unable to load config.json")
            return
        if not "geo" in config: config['geo'] = {}
        requestIP = config['connectivity']['ipv4'] if config['connectivity']['ipv4'] else config['connectivity']['ipv6']
        headers = {"Origin":"https://ip-api.com"}
        ipapi, ipapiDataRaw = self.call(f"https://demo.ip-api.com/json/{requestIP}?fields=66842623&lang=en",{},"GET",headers)
        ipwhois, ipwhoisDataRaw = self.call(f"https://ipwho.is/{requestIP}",{},"GET")
        if ipapi:
            ipapiData = ipapiDataRaw.json()
            config['geo']['countryCode'] = ipapiData['countryCode']
            config['geo']['continent'] = ipapiData['continent']
            config['geo']['country'] = ipapiData['country']
            config['geo']['city'] = ipapiData['city']
            config['geo']['lat'] = ipapiData['lat']
            config['geo']['lon'] = ipapiData['lon']
        if ipwhois:
            ipwhoisData = ipwhoisDataRaw.json()
            if not ipapi or ipapiData['countryCode'] != ipwhoisData['country_code'] or ipapiData['city'] != ipwhoisData['city']:
                print("ipwho.is suggests, the location reported by ip-api is wrong")
                config['geo']['countryCode'] = ipwhoisData['country_code']
                config['geo']['continent'] = ipwhoisData['continent']
                config['geo']['country'] = ipwhoisData['country']
                config['geo']['city'] = ipwhoisData['city']
                config['geo']['lat'] = ipwhoisData['latitude']
                config['geo']['lon'] = ipwhoisData['longitude']
        print(f"Updated geodata {config['geo']}")
        self.saveJson(config,f"{self.path}/configs/config.json")

    def recover(self):
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.DEBUG)
        logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',datefmt='%d.%m.%Y %H:%M:%S',level=logging.DEBUG,handlers=[RotatingFileHandler(maxBytes=10000000,backupCount=5,filename=f"{self.path}/logs/recovery.log"),stream_handler])
        logger = logging.getLogger()
        self.bird = Bird(self.path,logger)
        self.bird.bird(True)

    def token(self):
        tokens = self.readJson(f"{self.path}/tokens.json")
        if tokens:
            print(f"Connect: {', '.join(tokens['connect'])}")
            print(f"Peer: {', '.join(tokens['peer'])}")
        else:
            print("Unable to load the tokens.json")

    def status(self):
        print("--- Services ----")
        proc = self.cmd("systemctl status bird")[0]
        birdRunning = "Bird2 is not running." if not "running" in proc else "Bird2 is running."
        proc = self.cmd("systemctl status wgmesh")[0]
        wgmeshRunning = "wgmesh is not running." if not "running" in proc else "wgmesh is running."
        proc = self.cmd("systemctl status wgmesh-bird")[0]
        wgmeshBirdRunning = "wgmesh-bird is not running." if not "running" in proc else "wgmesh-bird is running."
        print(f"{birdRunning}\t{wgmeshRunning}\t{wgmeshBirdRunning}")
        print("--- Wireguard ---")
        network = self.readJson(f"{self.path}/configs/network.json")
        if not network:
            print("Unable to load network.json")
            return
        print("Destination\tStatus\tPacketloss\tJitter")
        jittar,loss,online,offline = 0,0,0,0
        for dest,data in network.items():
            hasLoss,hasJitter = "No","No"
            if dest == "updated": continue
            if data['packetloss']:
                hasLoss = "Yes"
                loss += 1
            if data['jitter']:
                hasJitter = "Yes"
                jittar += 1
            if data['state']:
                state = "Online"
                online += 1
            else:
                state = "Offline"
                offline += 1
            print(f"{dest}\t{state}\t{hasLoss}\t\t{hasJitter}")
        print(f"{len(network) -1}\t\t{online}/{offline}\t{loss}\t\t{jittar}")

    def disable(self,option):
        config = self.readJson(f"{self.path}/configs/config.json")
        if not config:
            print("Unable to load config.json")
            return
        if "mesh" in option:
            self.wg.saveJson({},f"{self.path}/configs/state.json")
        elif "ospfv2" in option:
            config['bird']['ospfv2'] = False
        elif "ospfv3" in option:
            config['bird']['ospfv3'] = False
        elif "jitter" in option:
            config['bird']['jitter'] = False
        elif "client" in option:
            config['bird']['client'] = False
        elif "notifications" in option:
            config['notifications']['enabled'] = False
        elif "wgobfs" in option:
            if "wgobfs" in config['linkTypes']: config['linkTypes'].remove("wgobfs")
        elif "ipt_xor" in option:
            if "ipt_xor" in config['linkTypes']: config['linkTypes'].remove("ipt_xor")
        elif "amneziawg" in option or "awg" in option:
            if "amneziawg" in config['linkTypes']: config['linkTypes'].remove("amneziawg")
        elif "neighbour" in option:
            config['modules']['neighbour'] = False
        elif "update" in option:
            config['modules']['update'] = False
        else:
            print("Valid options: mesh, ospfv2, ospfv3, jitter, wgobfs, ipt_xor, amneziawg / awg, client, notifications, neighbour, update")
            return
        response = self.saveJson(config,f"{self.path}/configs/config.json")
        if not response:
            print("Failed to save config.json")
            return
        print("You should reload the services to apply any config changes")
            
    def enable(self,option):
        config = self.readJson(f"{self.path}/configs/config.json")
        if not config:
            print("Unable to load config.json")
            return
        if "mesh" in option:
            if os.path.isfile(f"{self.path}/configs/state.json"): os.remove(f"{self.path}/configs/state.json")
        elif "ospfv2" in option:
            config['bird']['ospfv2'] = True
        elif "ospfv3" in option:
            config['bird']['ospfv3'] = True
        elif "jitter" in option:
            config['bird']['jitter'] = True
        elif "client" in option:
            config['bird']['client'] = True
        elif "notifications" in option:
            config['notifications']['enabled'] = True
        elif "wgobfs" in option:
            if not "wgobfs" in config['linkTypes']: config['linkTypes'].append("wgobfs")
            print("You still need to install wgobfs with: bash /opt/wg-mesh/tools/wgobfs.sh")
        elif "ipt_xor" in option:
            if not "ipt_xor" in config['linkTypes']: config['linkTypes'].append("ipt_xor")
            print("You still need to install ipt_xor with: bash /opt/wg-mesh/tools/xor.sh")
        elif "amneziawg" in option or "awg" in option:
            if not "amneziawg" in config['linkTypes']: config['linkTypes'].append("amneziawg")
            print("You still need to install amneziawg with: bash /opt/wg-mesh/tools/amnezia.sh")
        elif "neighbour" in option:
            config['modules']['neighbour'] = True
        elif "update" in option:
            config['modules']['update'] = True
        else:
            print("Valid options: mesh, ospfv2, ospfv3, jitter, wgobfs, ipt_xor, amneziawg / awg, client, notifications, neighbour, update")
            return
        response = self.saveJson(config,f"{self.path}/configs/config.json")
        if not response:
            print("Failed to save config.json")
            return
        print("You should reload the services to apply any config changes")

    def setOption(self,options):
        validOptions = ["prefix","defaultLinkType","basePort","tick","reloadInterval","hello","operationMode","networkID","loglevel","vxlanOffset","subnet","subnetv6","subnetVXLAN","subnetPeer","subnetPeerv6","AllowedPeers","gotifyUp","gotifyDown","gotifyError",'gotifyDiag','gotifyChanges','blacklist']
        if len(sys.argv) == 0:
            print(f"Valid options: {', '.join(validOptions)}")
        else:
            key, value = options
            if key in validOptions:
                config = self.readJson(f"{self.path}/configs/config.json")
                if not config:
                    print(f"Unable to read config.json")
                    return
                if key == "basePort" or key == "vxlanOffset" or key == "operationMode" or key == "networkID":
                    config[key] = int(value)
                elif key == "tick" or key == "reloadInterval" or key == "hello":
                    config['bird'][key] = int(value)
                elif key == "gotifyUp" or key == "gotifyDown" or key == "gotifyError" or key == "gotifyDiag" or key == "gotifyChanges":
                    config['notifications'][key] = value
                elif key == "AllowedPeers":
                    if value in config['AllowedPeers']:
                        config['AllowedPeers'].remove(value)
                    else:
                        config['AllowedPeers'].append(value)
                elif key == "blacklist":
                    if value in config['connectivity']['blacklist']:
                        config['connectivity']['blacklist'].remove(value)
                    else:
                        config['connectivity']['blacklist'].append(value)
                else:
                    #rewrite awg to amneziawg
                    if key == "defaultLinkType" and value == "awg": 
                        value = "amneziawg"
                    config[key] = value
                response = self.saveJson(config,f"{self.path}/configs/config.json")
                if not response:
                    print("Failed to save config.json")
                    return
                print("You should reload the services to apply any config changes")
                if key == "subnet" or key == "subnetVXLAN":        
                    print("Reconfiguring dummy")
                    self.wg = Wireguard(self.path)
                    self.wg.reconfigureDummy()
            else:
                print(f"Valid options: {', '.join(validOptions)}")
        
    def cost(self,link,cost=0):
        self.wg.setCost(link,cost)

    def debug(self,targetLink):
        self.wg = Wireguard(self.path)
        links = self.wg.getLinks()
        mapping = {}
        for currentLink, details in links.items():
            if f"{targetLink}.sh" == currentLink:
                mapping = {details['remote']:"Remote",details['vxlan']:"VXLAN",details['remotePublic']:"Public"}
                targets = [details['vxlan'],details['remote'],details['remotePublic']]
                fping = self.wg.fping(targets,3,True)
                break
        if not mapping: return
        print("Ping results")
        for ip, pings in fping.items():
            print(f"{mapping[ip]}: {len(pings)} of 3 ({ip})")
        if details['remotePublic']:
            print(f"Running MTR to {details['remotePublic']}")
            mtr = self.cmd(f'mtr {details["remotePublic"]} --report --report-cycles 5')
            if not mtr[0] and mtr[1]: mtr[0] = mtr[1]
            print(mtr[0])