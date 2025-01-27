import urllib.request, ipaddress, requests, random, string, json, time, re, os
from Class.templator import Templator
from Class.network import Network
from Class.base import Base

class Wireguard(Base):
    Templator = Templator()

    def __init__(self,path,skip=False,onlyConfig=False):
        self.path = path
        self.isInitial = False
        if skip: return
        if not os.path.isfile(f"{self.path}/configs/config.json"): exit("Config missing")
        self.config = self.readJson(f'{self.path}/configs/config.json')
        if onlyConfig: return
        self.Network = Network(self.config)
        self.prefix = self.config['prefix']
        self.subnetPrefix = ".".join(self.config['subnet'].split(".")[:2])
        self.subnetPrefixSplitted = self.config['subnet'].split(".")
        self.subnetPeerPrefix = ".".join(self.config['subnetPeer'].split(".")[:2])
        self.subnetPeerPrefixSplitted = self.config['subnetPeer'].split(".")

    def updateConfig(self):
        reconfigureDummy = False
        if not "defaultLinkType" in self.config: self.config['defaultLinkType'] = "default"
        if not "listenPort" in self.config: self.config['listenPort'] = 8080
        if not "operationMode" in self.config: self.config['operationMode'] = 0
        if not "vxlanOffset" in self.config: self.config['vxlanOffset'] = 0
        if not "subnet" in self.config: self.config['subnet'] = "10.0.0.0/16"
        if not "subnetPeer" in self.config: self.config['subnetPeer'] = "172.31.0.0/16"
        if not "subnetVXLAN" in self.config: 
            self.config['subnetVXLAN'] = "10.0.251.0/24"
            reconfigureDummy = True
        if not "subnetLinkLocal" in self.config: self.config['subnetLinkLocal'] = "fe82:"
        if not "AllowedPeers" in self.config: self.config['AllowedPeers'] = []
        if not "linkTypes" in self.config: self.config['linkTypes'] = ["default"]
        if not os.path.isfile("/etc/bird/static.conf"): self.cmd('touch /etc/bird/static.conf')
        if not os.path.isfile("/etc/bird/bgp.conf"): self.cmd('touch /etc/bird/bgp.conf')
        if not "bird" in self.config: self.config['bird'] = {}
        if not "ospfv2" in self.config['bird']: self.config['bird']['ospfv2'] = True
        if not "ospfv3" in self.config['bird']: self.config['bird']['ospfv3'] = True
        if not "area" in self.config['bird']: self.config['bird']['area'] = 0
        if not "tick" in self.config['bird']: self.config['bird']['tick'] = 1
        if not "client" in self.config['bird']: self.config['bird']['client'] = False
        if not "loglevel" in self.config['bird']: self.config['bird']['loglevel'] = "{ warning, fatal}"
        if not "reloadInterval" in self.config['bird']: self.config['bird']['reloadInterval'] = 600
        if not "notifications" in self.config: self.config['notifications'] = {"enabled":False,"gotifyUp":"","gotifyDown":""}
        if not "gotifyError" in self.config['notifications']: self.config['notifications']['gotifyError'] = ""
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

    def getConfigs(self,abort=True):
        files = os.listdir(f'{self.path}/links/')
        for file in list(files):
            if not file.endswith(".sh"): files.remove(file)
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
        connectivity = {"ipv4":ipv4,"ipv6":ipv6}
        config = {"listen":listen,"listenPort":8080,"basePort":51820,"operationMode":0,"vxlanOffset":0,"subnet":"10.0.0.0/16","subnetPeer":"172.31.0.0/16",
        "subnetVXLAN":"10.0.251.0/24","subnetLinkLocal":"fe82:","AllowedPeers":[],"prefix":"pipe","id":int(id),"linkTypes":["default"],"defaultLinkType":"default","connectivity":connectivity,
        "bird":{"ospfv2":True,"ospfv3":True,"area":0,"tick":1,"client":False,"loglevel":"{ warning, fatal}","reloadInterval":600},"notifications":{"enabled":False,"gotifyUp":"","gotifyDown":"","gotifyError":""}}
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

    def minimal(self,files,port=51820):
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
            peerSubnets = self.Network.getPeerSubnets()
            peerSubnetsv6 = self.Network.getPeerSubnetsv6()
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

    def getInterface(self,id,type="",network=""):
        return f"{self.prefix}{network}{id}{type}"

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

    def removeInterface(self,interface):
        self.setInterface(interface,"down")
        self.cleanInterface(interface)

    def clean(self,ignoreJSON,ignoreEndpoint):
        links =  self.getLinks(True,ignoreJSON)
        offline,online = self.checkLinks(links)
        for link in offline:
            data = links[link]
            parsed, remote = self.getRemote(data['config'],self.subnetPrefixSplitted)
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
            subnetPrefix,subnetPrefixSplitted = self.subnetSwitch(filename)
            if linkConfig and useJSON:
                remotePublic = linkConfig['remotePublic']
                destination = linkConfig['remote']
            else:
                remotePublic = ""
                destination = ""
                #grab wg server ip from client wg config
                if "endpoint" in config:
                    remotePublic = re.findall(f'endpoint\s(.*):',config, re.MULTILINE)[0]
                    destination = re.findall(f'({subnetPrefixSplitted[0]}\.{subnetPrefixSplitted[1]}\.[0-9]+\.)',config, re.MULTILINE)
                    if not destination:
                        print(f"Ignoring {filename}")
                        continue
                    destination = f"{destination[0]}1"
                elif "Peer" in filename:
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
            local, remote = self.getRemote(config,subnetPrefixSplitted)
            #grab publickey
            publicKey = re.findall(f"peer\s([A-Za-z0-9/.=+]+)",config,re.MULTILINE)[0]
            #grab area
            area = re.findall(f"Area\s([0-9]+)",config,re.MULTILINE)
            area = int(area[0]) if area else 0
            links[filename] = {"filename":filename,"vxlan":destination,"local":local,"remote":remote,'remotePublic':remotePublic,'publicKey':publicKey,"area":area,"config":config}
        return links

    def AskProtocol(self,dest,token=""):
        #ask remote about available protocols
        req = self.call(f'{dest}/connectivity',{"token":token})
        if req == False: return False
        if req.status_code != 200:
            print("Failed to request connectivity info")
            return False
        data = req.json()
        return data

    def subnetSwitch(self,network=""):
        if "Peer" in network:
            return self.subnetPeerPrefix,self.subnetPeerPrefixSplitted
        else:
            return self.subnetPrefix,self.subnetPrefixSplitted

    def connect(self,dest,token="",linkType="",port=51820,network=""):
        print(f"Connecting to {dest}")
        #generate new key pair
        clientPrivateKey, clientPublicKey = self.genKeys()
        #initial check
        configs = self.cmd('ip addr show')[0]
        subnetPrefix,subnetPrefixSplitted = self.subnetSwitch(network)
        links = self.getBirdLinks(configs,self.prefix,subnetPrefixSplitted)
        self.isInitial = False if links else True
        status = {"v4":False,"v6":False}
        #ask remote about available protocols
        data = self.AskProtocol(dest,token)
        if not data: return status
        #start with the protocol which is available
        if data['connectivity']['ipv4'] and self.config['connectivity']['ipv4']: isv6 = False
        elif data['connectivity']['ipv6'] and self.config['connectivity']['ipv6']: isv6 = True
        #if neither of these are available, leave it
        else: return status
        #linkType
        if linkType == "":
            if self.config['defaultLinkType'] in data['linkTypes']:
                linkType = self.config['defaultLinkType']
            else:
                linkType = "default"
        for run in range(2):
            #call destination
            payload = {"clientPublicKey":clientPublicKey,"id":self.config['id'],"token":token,
            "ipv6":isv6,"initial":self.isInitial,"linkType":linkType,"area":self.config['bird']['area'],"prefix":subnetPrefix,"network":network,"connectivity":self.config['connectivity']}
            if port != 51820: payload["port"] = port
            req = self.call(f'{dest}/connect',payload)
            if req == False: return status
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
                linkConfig = {'remote':f"{data['subnetPrefix']}.{resp['id']}.1",'remotePublic':connectivity.replace("[","").replace("]","")}
                self.saveJson(linkConfig,f"{self.path}/links/{interface}.json")
                self.setInterface(interface,"up")
                status["v6" if isv6 else "v4"] = True
            else:
                print(f"Failed to connect to {dest}")
                print(f"Got {req.text} as response")
                return status
            #before we try to setup a v4 in v6 wg, we check if booth hosts have IPv6 connectivity
            if not self.config['connectivity']['ipv6'] or not data['connectivity']['ipv6']: break
            if not self.config['connectivity']['ipv4'] or not data['connectivity']['ipv4']: break
            #second run going to be IPv6 if available
            isv6 = True
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
        targets = self.getRoutes(self.subnetPrefixSplitted)
        parsed = re.findall(f"([0-9]+).0\/30",", ".join(targets), re.MULTILINE)
        parsed.sort(key = int)
        return parsed

    def bender(self):
        print("Getting Routes")
        parsed = self.getUsedIDs()
        print("Route Bender nodes.json")
        for id in parsed: print(f'"{self.subnetPrefix}.252.{id}",')

    def used(self):
        print("Getting Routes")
        parsed = self.getUsedIDs()
        print("Already used ID's")
        print(parsed)

    def proximity(self,cutoff=0):
        fpingTargets, existing = [],[]
        links = self.getLinks()
        for link,details in links.items(): existing.append(details['vxlan'])
        print("Getting Routes")
        targets = self.getRoutes(self.subnetPrefixSplitted)
        print("Getting Connection info")
        ips = {}
        local = f"{self.subnetPrefix}.{self.config['id']}.1"
        for target in targets:
            target = target.replace("0/30","1")
            if target == local:
                print(f"Skipping {target} since local.")
                continue
            resp = self.AskProtocol(f'http://{target}:{self.config["listenPort"]}','')
            if not resp: continue
            ips[resp['connectivity']['ipv4']] = target
            ips[resp['connectivity']['ipv6']] = target
        for ip in ips:
            if ip != None: fpingTargets.append(ip)
        print("Getting Latency")
        fping = self.fping(fpingTargets,10)
        latencyData = {}
        print("Parsing Results")
        for ip in fping: latencyData[ip] = self.getAvrg(fping[ip])
        latencyData = {k: latencyData[k] for k in sorted(latencyData, key=latencyData.get)}
        terminate, result = [], []
        result.append("Target\tIP address\tConnected\tLatency")
        result.append("-------\t-------\t-------\t-------")
        for ip,latency in latencyData.items(): 
            if latency > float(cutoff): terminate.append(ips[ip])
            result.append(f"{ips[ip]}\t{ip}\t{bool(ips[ip] in existing)}\t{latency}ms")
        result = self.formatTable(result)
        if cutoff == 0: 
            print(result)
            return True
        for ip,latency in latencyData.items():
            if latency > float(cutoff): continue 
            targetSplit = ips[ip].split(".")
            #reserve 10.0.200+ for clients, don't mesh
            if int(targetSplit[2]) >= 200: continue
            if ips[ip] in existing: continue
            self.connect(f"http://{ips[ip]}:{self.config['listenPort']}")
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
            #call destination
            if not filename in currentLinks: 
                print(f"Unable to find link {filename}")
                status[filename] = False
                continue
            data = currentLinks[filename]
            print(f'Calling http://{data["vxlan"]}:{self.config["listenPort"]}/disconnect')
            req = self.call(f'http://{data["vxlan"]}:{self.config["listenPort"]}/disconnect',{"publicKeyServer":data['publicKey'],"interface":interfaceRemote})
            if req == False and force == False: continue
            if force or req.status_code == 200:
                interface = self.filterInterface(filename)
                self.removeInterface(interface)
                status[filename] = True
            else:
                print(f"Got {req.status_code} with {req.text} aborting")
                status[filename] = False
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