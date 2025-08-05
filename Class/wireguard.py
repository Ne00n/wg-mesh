import urllib.request, ipaddress, requests, random, string, json, time, re, os
from Class.templator import Templator
from Class.validate import Validate
from Class.network import Network
from Class.base import Base

class Wireguard(Base):
    Templator = Templator()

    def __init__(self,path,skip=False,onlyConfig=False):
        super().__init__()
        self.path = path
        self.isInitial = False
        if skip: return
        if not os.path.isfile(f"{self.path}/configs/config.json"): exit("Config missing")
        self.config = self.readJson(f'{self.path}/configs/config.json')
        if onlyConfig: return
        self.amneziaConfig = {}
        self.Network = Network(self.config)
        self.prefix = self.config['prefix']
        self.validate = Validate()

    def updateConfig(self):
        reconfigureDummy = False
        if not "defaultLinkType" in self.config: self.config['defaultLinkType'] = "default"
        if not "listenPort" in self.config: self.config['listenPort'] = 8080
        if not "operationMode" in self.config: self.config['operationMode'] = 0
        if not "loglevel" in self.config: self.config['loglevel'] = "info"
        if not "vxlanOffset" in self.config: self.config['vxlanOffset'] = 0
        if not "networkID" in self.config: self.config['networkID'] = 0
        if not "subnet" in self.config: self.config['subnet'] = "10.0.0.0/16"
        if not "subnetv6" in self.config: self.config['subnetv6'] = "fe82:"
        if not "subnetPeer" in self.config: self.config['subnetPeer'] = "172.31.0.0/16"
        if not "subnetPeerv6" in self.config: self.config['subnetPeerv6'] = "fe81:"
        if not "subnetVXLAN" in self.config: 
            self.config['subnetVXLAN'] = "10.0.251.0/24"
            reconfigureDummy = True
        if not "blacklist" in self.config['connectivity']: self.config['connectivity']['blacklist'] = []
        if not "AllowedPeers" in self.config: self.config['AllowedPeers'] = []
        if not "linkTypes" in self.config: self.config['linkTypes'] = ["default"]
        if not os.path.isfile("/etc/bird/static.conf"): self.cmd('touch /etc/bird/static.conf')
        if not os.path.isfile("/etc/bird/bgp.conf"): self.cmd('touch /etc/bird/bgp.conf')
        if not "bird" in self.config: self.config['bird'] = {}
        if not "modules" in self.config: self.config['modules'] = {"neighbour":False,"update":False}
        if not "linkSettings" in self.config: self.config['linkSettings'] = {"awgGen":False}
        if not "latency" in self.config: self.config['latency'] = {"pingInterval":30}
        if not "ospfv2" in self.config['bird']: self.config['bird']['ospfv2'] = True
        if not "ospfv3" in self.config['bird']: self.config['bird']['ospfv3'] = True
        if not "jitter" in self.config['bird']: self.config['bird']['jitter'] = True
        if not "area" in self.config['bird']: self.config['bird']['area'] = 0
        if not "tick" in self.config['bird']: self.config['bird']['tick'] = 1
        if not "client" in self.config['bird']: self.config['bird']['client'] = False
        if not "loglevel" in self.config['bird']: self.config['bird']['loglevel'] = "{ warning, fatal}"
        if not "reloadInterval" in self.config['bird']: self.config['bird']['reloadInterval'] = 600
        if not "notifications" in self.config: self.config['notifications'] = {"enabled":False,"gotifyUp":"","gotifyDown":"","gotifyError":"","gotifyDiag":"","gotifyChanges":""}
        if not "gotifyChanges" in self.config['notifications']: self.config['notifications']['gotifyChanges'] = ""
        if not "gotifyDiag" in self.config['notifications']: self.config['notifications']['gotifyDiag'] = ""
        self.saveJson(self.config,f"{self.path}/configs/config.json")
        if reconfigureDummy: self.reconfigureDummy()

    def genKeys(self):
        keys = self.cmd('key=$(wg genkey) && echo $key && echo $key | wg pubkey')[0]
        privateKeyServer, publicKeyServer = keys.splitlines()
        return privateKeyServer, publicKeyServer

    def genPreShared(self):
        return self.cmd('wg genpsk')[0]

    def getConfig(self):
        return self.config

    def getPublic(self,private):
        return self.cmd(f'echo {private} | wg pubkey')[0].rstrip()

    def loadConfigs(self,files):
        configs = []
        for config in files: configs.append(self.readFile(f'{self.path}/links/{config}'))
        return configs

    def getConfigs(self,abort=True,isPeer=False):
        files = os.listdir(f'{self.path}/links/')
        for file in list(files):
            if not file.endswith(".sh"): 
                files.remove(file)
                continue
            if isPeer and not "tunnel" in file: files.remove(file)
        if not files and abort: exit(f"No {self.prefix} configs found")
        return files

    def fetch(self,url):
        try:
            request = urllib.request.urlopen(url, timeout=3)
            if (request.getcode() != 200): 
                print(f"Failed to fetch {url}")
                return
        except:
            return
        return request.read().decode('utf-8').strip() 

    def getIP(self,config):
        for key,ip in config['connectivity'].items():
            if ip is not None: return ip

    def init(self,id,listen):
        if os.path.isfile(f"{self.path}/config.json"): exit("Config already exists")
        print("Getting external IPv4 and IPv6")
        ipv4 = self.fetch("https://checkip.amazonaws.com")
        ipv6 = self.fetch("https://api6.ipify.org/")
        print(f"Got {ipv4} and {ipv6}")
        #config
        print("Generating config.json")
        connectivity = {"ipv4":ipv4,"ipv6":ipv6,"blacklist":[]}
        config = {"listen":listen,"listenPort":8080,"basePort":51820,"operationMode":0,"loglevel":"info","vxlanOffset":0,"subnet":"10.0.0.0/16","subnetv6":"fe82:","subnetPeer":"172.31.0.0/16","subnetPeerv6":"fe81:",
        "subnetVXLAN":"10.0.251.0/24","AllowedPeers":[],"prefix":"pipe","id":int(id),"networkID":0,"linkTypes":["default"],"linkSettings":{"awgGen":False},"defaultLinkType":"default","connectivity":connectivity,
        "bird":{"ospfv2":True,"ospfv3":True,"jitter":True,"area":0,"tick":1,"client":False,"loglevel":"{ warning, fatal}","reloadInterval":600},
        "modules":{"neighbour":False,"update":False},"latency":{"pingInterval":30},
        "notifications":{"enabled":False,"gotifyUp":"","gotifyDown":"","gotifyError":"","gotifyDiag":"","gotifyChanges":""}}
        response = self.saveJson(config,f"{self.path}/configs/config.json")
        if not response: exit("Unable to save config.json")
        #load configs
        self.prefix = "pipe"
        configs = self.getConfigs(False)
        #dummy
        if not "dummy.sh" in configs:
            dummyConfig = self.Templator.genDummy(config,connectivity)
            self.saveFile(dummyConfig,f"{self.path}/links/dummy.sh")
            self.setInterface("dummy","up")

    def reconfigureDummy(self):
        self.setInterface("dummy","down")
        self.cleanInterface("dummy",False)
        dummyConfig = self.Templator.genDummy(self.config,self.config['connectivity'])
        self.saveFile(dummyConfig,f"{self.path}/links/dummy.sh")
        self.setInterface("dummy","up")

    def findLowest(self,min,list):
        for i in range(min,min + 400):
            if i not in list and i % 2 == 0: return i

    def minimal(self,files,port=51820,isPeer=False):
        ports,usedSubnets,usedSubnetsv6,freeSubnet = [],[],[],""
        if port == 0: port = random.randint(1500, 55000)
        for file in files:
            config = self.readFile(f"{self.path}/links/{file}")
            configPort = re.findall(f"listen-port\s([0-9]+)",config, re.MULTILINE)
            configIP = re.findall(f"ip address add dev.*?([0-9.]+\/31)",config, re.MULTILINE)
            configIPv6 = re.findall(f"ip -6 address add dev.*?([a-zA-Z0-9:]+\/127)",config,re.MULTILINE)
            #Clients are ignored since they use a different subnet
            if not configPort: continue
            ports.append(int(configPort[0]))
            usedSubnets.append(configIP[0])
            usedSubnetsv6.append(configIPv6[0])
        freePort = self.findLowest(port,ports)
        try:
            #Get available subnets
            peerSubnets = self.Network.getPeerSubnets(isPeer)
            peerSubnetsv6 = self.Network.getPeerSubnetsv6(isPeer)
            #Convert to network objects
            usedSubnets = {ipaddress.ip_network(subnet) for subnet in usedSubnets}
            usedSubnetsv6 = {ipaddress.ip_network(subnet) for subnet in usedSubnetsv6}
            #Find usable subnets
            freeSubnets = set(peerSubnets) - usedSubnets
            freeSubnetsv6 = set(peerSubnetsv6) - usedSubnetsv6
            for subnet in sorted(freeSubnets, key=lambda x: int(x.network_address)):
                freeSubnet = str(subnet)
                break
            for subnet in sorted(freeSubnetsv6, key=lambda x: int(x.network_address)):
                freeSubnetv6 = str(subnet)
                break
            return freeSubnet,freeSubnetv6,freePort
        except:
            return "","",0

    def getInterface(self,id,type="",network="",prefix=""):
        if not prefix: prefix = self.prefix
        return f"{prefix}{network}{id}{type}"

    def filterInterface(self,interface):
        return interface.replace(".sh","")

    def getInterfaceRemote(self,interface,network=""):
        v6 = "v6" if "v6" in interface else ""
        return f"{self.prefix}{network}{self.config['id']}{v6}"

    def setInterface(self,file,state):
        self.cmd(f'bash {self.path}/links/{file}.sh {state}')

    def cleanInterface(self,interface,deleteKey=True):
        os.remove(f"{self.path}/links/{interface}.sh")
        if deleteKey:
            os.remove(f"{self.path}/links/{interface}.key")
            if os.path.isfile(f"{self.path}/links/{interface}.pre"): os.remove(f"{self.path}/links/{interface}.pre")
            if os.path.isfile(f"{self.path}/links/{interface}.json"): os.remove(f"{self.path}/links/{interface}.json")

    def createInterface(self,interface,privateKey,preSharedKey,config,linkConfig):
        self.saveFile(privateKey,f"{self.path}/links/{interface}.key")
        self.saveFile(preSharedKey,f"{self.path}/links/{interface}.pre")
        self.saveFile(config,f"{self.path}/links/{interface}.sh")
        self.saveJson(linkConfig,f"{self.path}/links/{interface}.json")

    def removeInterface(self,interface):
        self.setInterface(interface,"down")
        self.cleanInterface(interface)

    def clean(self,ignoreJSON,ignoreEndpoint):
        links =  self.getLinks(True,ignoreJSON)
        offline,online = self.checkLinks(links)
        for link in offline:
            data = links[link]
            parsed, remote = self.getRemote(data['config'],self.Network.getSubnetSplitted())
            print(f"Found dead link {link} ({remote})")
            pings = self.fping([data['vxlan']],3,True)
            if ignoreEndpoint or not pings or not pings[data['vxlan']]:
                print(f"Unable to reach endpoint {link} ({data['vxlan']})")
                print(f"Removing {link} ({data['vxlan']})")
                interface = self.filterInterface(link)
                self.removeInterface(interface)
            else:
                print(f"Endpoint {data['vxlan']} still up, ignoring.")

    def getFilename(self,links,remote):
        for filename, row in links.items():
            if row['remote'] == remote: return filename

    def filesToLinks(self,files,useJSON=True):
        links = {}
        for findex, filename in enumerate(files):
            if not filename.endswith(".sh") or filename == "dummy.sh": continue
            config = self.readFile(f"{self.path}/links/{filename}")
            if not config:
                print(f"{filename} is empty!")
                continue
            link = filename.replace(".sh","")
            linkConfig = self.readJson(f"{self.path}/links/{link}.json")
            subnetSplitted,subnetPrefix = self.Network.subnetSwitch(filename)
            if linkConfig and useJSON:
                remotePublic = linkConfig['remotePublic']
                destination = linkConfig['remote']
            else:
                remotePublic = ""
                destination = ""
                #grab wg server ip from client wg config
                if "endpoint" in config:
                    remotePublic = re.findall(f'endpoint\s(.*):',config, re.MULTILINE)[0]
                    destination = re.findall(f'({subnetSplitted[0]}\.{subnetSplitted[1]}\.[0-9]+\.)',config, re.MULTILINE)
                    if not destination:
                        print(f"Ignoring {filename}")
                        continue
                    destination = f"{destination[0]}1"
                elif "peer" in filename:
                    peerIP = re.findall("Peer\s([0-9.]+)",config, re.MULTILINE)
                    if not peerIP:
                        print(f"Unable to figure out peer for {filename}")
                        continue
                    destination = peerIP[0]
                elif "listen-port" in config:
                    #grab ID from filename
                    linkID = re.findall(f"{self.prefix}.*?([0-9]+)",filename, re.MULTILINE)[0]
                    destination = f"{subnetPrefix}.{linkID}.1"
            #get remote endpoint
            local, remote = self.getRemote(config,subnetSplitted)
            #grab publickey
            publicKey = re.findall(f"peer\s([A-Za-z0-9/.=+]+)",config,re.MULTILINE)[0]
            #grab area
            area = re.findall(f"Area\s([0-9]+)",config,re.MULTILINE)
            area = int(area[0]) if area else 0
            links[filename] = {"filename":filename,"vxlan":destination,"local":local,"remote":remote,'remotePublic':remotePublic,'publicKey':publicKey,"area":area,"config":config}
        return links

    def genAmneziaConfig(self):
        self.amneziaConfig = config = {}
        #vanillaAmnezia switch
        vanilla = random.randint(0, 1)
        if vanilla: return config
        #junkPackage switch
        junkPackages = random.randint(0, 1)
        if junkPackages:
            #number of junk packages
            config['jc'] = random.randint(2, 5)
            #junk package minimum size
            config['jmin'] = random.randint(10, 50)
            #junk package maximum size
            config['jmax'] = random.randint(config['jmin'] + 50, 1000)
        #junk in handshake
        numbers = random.sample(range(15,150), 2)
        config['s1'] = numbers[0]
        config['s2'] = numbers[1]
        #user defined types
        numbers = random.sample(range(15,2147483647), 4)
        config['h1'] = numbers[0]
        config['h2'] = numbers[1]
        config['h3'] = numbers[2]
        config['h4'] = numbers[3]
        self.amneziaConfig = config
        return config

    def getAmneziaConfig(self):
        return self.amneziaConfig

    def AskProtocol(self,dest,token=""):
        #ask remote about available protocols
        success, req = self.call(f'{dest}/connectivity',{"token":token})
        if success == False: return False
        if req.status_code != 200:
            print("Failed to request connectivity info")
            return False
        data = req.json()
        return data

    def getNeighbours(self):
        lines = self.cmd('birdc show route')[0]
        routes = lines.splitlines()
        neighbours = {}
        for index, line in enumerate(routes):
            if ".0/30" in line and not "direct" in line:
                id = re.findall(r"([0-9]+)\.0\/30",line,re.MULTILINE | re.DOTALL)[0]
                cost = re.findall(r"\([0-9]+/([0-9]+)/[0-9]+\)",line,re.MULTILINE | re.DOTALL)[0]
                nextLine = routes[index +1]
                if f"pipe{id}" in nextLine: neighbours[id] = int(cost) / 10
        return neighbours

    def availableLinkTypes(self,local,remote):
        available = []
        for linkType in remote['linkTypes']:
            if linkType in local['linkTypes']: available.append(linkType)
        return available

    def connect(self,dest,token="",linkType="",port=51820,network=""):
        print(f"Connecting to {dest}")
        #generate new key pair
        clientPrivateKey, clientPublicKey = self.genKeys()
        #initial check
        configs = self.cmd('ip addr show')[0]
        subnetSplitted,subnetPrefix = self.Network.subnetSwitch(network)
        links = self.getBirdLinks(configs,self.prefix,subnetSplitted)
        self.isInitial = False if links else True
        status = {"ipv4":{"status":False,"http":0},"ipv6":{"status":False,"http":0}}
        #ask remote about available protocols
        data = self.AskProtocol(dest,token)
        if not data: return status
        availableProtocols = []
        #start with the protocol which is available
        if data['connectivity']['ipv4'] and self.config['connectivity']['ipv4']:
            availableProtocols.append("ipv4")
        if data['connectivity']['ipv6'] and self.config['connectivity']['ipv6']:
            availableProtocols.append("ipv6")
        #if neither of these are available, leave it
        if not availableProtocols: return status
        #linkType
        if linkType == "":
            if self.config['defaultLinkType'] in data['linkTypes']:
                linkType = self.config['defaultLinkType']
            else:
                linkType = "default"
        else:
            if not linkType in data['linkTypes']:
                linkType = "default"
        for protocol in availableProtocols:
            isv6 = True if protocol == "ipv6" else False
            #call destination
            payload = {"clientPublicKey":clientPublicKey,"id":self.config['id'],"token":token,
            "ipv6":isv6,"initial":self.isInitial,"linkType":linkType,"area":self.config['bird']['area'],"prefix":subnetPrefix,"network":network,"connectivity":self.config['connectivity']}
            if port != 51820: payload["port"] = port
            success, req = self.call(f'{dest}/connect',payload)
            if success == False: return status
            status[protocol]['http'] = req.status_code
            if req.status_code == 412:
                print(f"Link already exists to {dest}")
            elif req.status_code == 200:
                resp = req.json()
                #check if v6 or v4
                interfaceType = "v6" if isv6 else ""
                connectivity =  f"[{resp['connectivity']['ipv6']}]"  if isv6 else resp['connectivity']['ipv4']
                #interface
                interface = self.getInterface(resp['id'],interfaceType,network)
                #generate config
                clientConfig = self.Templator.genClient(interface,self.config,resp,connectivity,linkType,subnetPrefix,data['subnetPrefix'])
                print(f"Creating & Starting {interface}")
                self.saveFile(clientPrivateKey,f"{self.path}/links/{interface}.key")
                self.saveFile(resp['preSharedKey'],f"{self.path}/links/{interface}.pre")
                self.saveFile(clientConfig,f"{self.path}/links/{interface}.sh")
                linkConfig = {'remote':f"{data['subnetPrefix']}.{resp['id']}.1",'remotePublic':connectivity.replace("[","").replace("]",""),"linkType":linkType}
                self.saveJson(linkConfig,f"{self.path}/links/{interface}.json")
                self.setInterface(interface,"up")
                status[protocol]['status'] = True
                #updating networkID on initial setup
                if 'networkID' in resp and resp['networkID'] != 0 and self.isInitial and self.validate.id(resp['networkID']):
                    self.config['networkID'] = resp['networkID']
                    self.saveJson(self.config,f'{self.path}/configs/config.json')
            else:
                print(f"Failed to connect to {dest}")
                print(f"Got {req.text} as response")
                return status
        return status

    def updateLink(self,link,data):
        config = self.readFile(f"{self.path}/links/{link}.sh")
        if 'port' in data: config = re.sub(f"listen-port ([0-9]+)", f"listen-port {data['port']}", config, 0, re.MULTILINE)
        if 'xorKey' in data: 
            xorKey = data['xorKey']
            config = re.sub(f'--keys."(.*?)"', f'--keys "{xorKey}"', config, 0, re.MULTILINE)
        if 'cost' in data: self.setCost(link,data['cost'])
        self.saveFile(config,f"{self.path}/links/{link}.sh")

    def getUsedIDs(self):
        targets = self.Network.getRoutes()
        parsed = re.findall(f"([0-9]+).0\/30",", ".join(targets), re.MULTILINE)
        parsed.sort(key = int)
        return parsed

    def bender(self):
        print("Getting Routes")
        parsed = self.getUsedIDs()
        print("Route Bender nodes.json")
        for id in parsed: print(f'"{self.Network.getSubnetPrefix()}.252.{id}",')

    def used(self):
        print("Getting Routes")
        parsed = self.getUsedIDs()
        print("Already used ID's")
        print(parsed)

    def proximity(self,cutoff=0):
        fpingTargets, existing = [],[]
        links = self.getLinks()
        for link,details in links.items(): existing.append(details['remotePublic'])
        print("Getting Routes")
        targets = self.Network.getRoutes()
        print("Getting Connection info")
        mapping = {}
        local = f"{self.Network.getSubnetPrefix()}.{self.config['id']}.1"
        for target in targets:
            target = target.replace("0/30","1")
            if target == local: 
                print(f"Skipping {target} since local.")
                continue
            resp = self.AskProtocol(f'http://{target}:{self.config["listenPort"]}','')
            if not resp: continue
            location = "n/a"
            if "geo" in resp and "city" in resp["geo"]: location = resp['geo']['city']
            if not resp['connectivity']['ipv4'] in mapping: mapping[resp['connectivity']['ipv4']] = {"target":target,"location":location}
            if not resp['connectivity']['ipv6'] in mapping: mapping[resp['connectivity']['ipv6']] = {"target":target,"location":location}
        for ip in mapping:
            if ip != None: fpingTargets.append(ip)
        print("Getting Latency")
        fping = self.fping(fpingTargets,10)
        latencyData = {}
        print("Parsing Results")
        for ip in fping: latencyData[ip] = self.getAvrg(fping[ip])
        latencyData = {k: latencyData[k] for k in sorted(latencyData, key=latencyData.get)}
        terminate, result = [], []
        result.append("Target\tIP address\tCity\tConnected\tLatency")
        result.append("-------\t-------\t-------\t-------\t-------")
        for ip,latency in latencyData.items(): 
            if latency > float(cutoff): terminate.append(mapping[ip]['target'])
            result.append(f"{mapping[ip]['target']}\t{ip}\t{mapping[ip]['location']}\t{bool(ip in existing)}\t{format(latency,'.2f')}ms")
        result = self.formatTable(result)
        if cutoff == 0: 
            print(result)
            return True
        for ip,latency in latencyData.items():
            if latency > float(cutoff): continue 
            targetSplit = mapping[ip]['target'].split(".")
            #reserve 10.0.200+ for clients, don't mesh
            if int(targetSplit[2]) >= 200: continue
            if ip in existing: continue
            self.connect(f"http://{mapping[ip]['target']}:{self.config['listenPort']}")
        for link,details in links.items():
            if not details['vxlan'] in terminate: continue
            self.disconnect([link])

    def getFiles(self):
        files = os.listdir(f"{self.path}/links/")
        return [x for x in files if self.filter(x)]

    def getLinks(self,shouldExit=True,useJSON=True):
        links = self.filesToLinks(self.getFiles(),useJSON)
        if not links and shouldExit: exit("No links found.")
        return links

    def groupByArea(self,latencyData):
        results = {}
        wgLinks = self.getLinks()
        for data in latencyData:
            if not f"{data['nic']}.sh" in wgLinks: continue
            current = wgLinks[f"{data['nic']}.sh"]
            if not current['area'] in results: results[current['area']] = []
            results[current['area']].append(data)
        return results

    def checkLinks(self,links):
        #fping
        fping = "fping -c2"
        for filename,row in links.items(): fping += f" {row['remote']}"
        results = self.cmd(fping)[1].splitlines()
        online,offline = [],[]
        #categorizing results
        for row in results:
            if "xmt/rcv/%loss" in row:
                ip = re.findall(f'([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)',row, re.MULTILINE)[0]
                filename = self.getFilename(links,ip)
                offline.append(filename) if "100%" in row else online.append(filename)
        return offline,online

    def disconnect(self,links=[],force=False):
        currentLinks, status = self.getLinks(),{}
        for index, link in enumerate(links):
            if not link.endswith(".sh"): links[index] += ".sh"
        if not links:
            print("Checking Links")
            offline,online = self.checkLinks(currentLinks)
            #shutdown the links that are offline first
            if offline: print(f"Found offline links, disconnecting them first. {offline}")
            targets = offline + online
        else:
            targets = links
        print("Disconnecting")
        for filename in targets:
            #if a specific link is given filter out
            if links and filename not in links: continue
            interfaceRemote = self.getInterfaceRemote(filename)
            if not filename in status: status[filename] = {"status":False,"http":0,"message":""}
            #call destination
            if not filename in currentLinks: 
                print(f"Unable to find link {filename}")
                status[filename]["message"] = "Unable to find link"
                continue
            data = currentLinks[filename]
            print(f'Calling http://{data["vxlan"]}:{self.config["listenPort"]}/disconnect')
            success, req = self.call(f'http://{data["vxlan"]}:{self.config["listenPort"]}/disconnect',{"publicKeyServer":data['publicKey'],"interface":interfaceRemote})
            if success == False and force == False and req is None: 
                continue
            if req is not None: status[filename]['http'] = req.status_code
            if force or req.status_code == 200:
                interface = self.filterInterface(filename)
                self.removeInterface(interface)
                status[filename]["status"] = True
            else:
                print(f"Got {req.status_code} with {req.text} aborting")
                status[filename]["message"] = req.text
        #load configs
        configs = self.getConfigs(False)
        #get all links
        files = os.listdir(f"{self.path}/links/")
        #check for dummy and .gitignore
        if "dummy.sh" in files: files.remove("dummy.sh")
        if ".gitignore" in files: files.remove(".gitignore")
        #clear state.json if no links left
        if os.path.isfile(f"{self.path}/configs/state.json") and not files:
            print("state.json has been reset!")
            os.remove(f"{self.path}/configs/state.json")
        return status

    def setCost(self,link,cost=0):
        if os.path.isfile(f"{self.path}/links/{link}.sh"):
            if not os.path.exists(f"{self.path}/pipe"):
                print("Pipe not found, did you start wgmesh-bird?")
                return
            with open(f"{self.path}/pipe", 'w') as f: f.write(json.dumps({"link":link,"cost":cost}))
            return True
        else:
            print(f"Unable to find file: {self.path}/links/{link}.sh")

    def getConfig(self):
        return self.config

    def getInitial(self):
        return self.isInitial