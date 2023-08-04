from Class.templator import Templator
import urllib.request, requests, random, string, json, time, re, os
from Class.base import Base

class Wireguard(Base):
    Templator = Templator()

    def __init__(self,path,skip=False):
        self.path = path
        if skip: return
        if not os.path.isfile(f"{self.path}/configs/config.json"): exit("Config missing")
        with open(f'{self.path}/configs/config.json') as f: self.config = json.load(f)
        self.prefix = self.config['prefix']

    def updateConfig(self):
        if not "defaultLinkType" in self.config: self.config['defaultLinkType'] = "default"
        if not "linkTypes" in self.config: self.config['linkTypes'] = ["default"]
        with open(f"{self.path}/configs/config.json", 'w') as f: json.dump(self.config, f ,indent=4)

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
        for config in files:
            with open(f'{self.path}/links/{config}') as f: configs.append(f.read())
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
        config = {"listen":listen,"basePort":51820,"prefix":"pipe","id":id,"linkTypes":["default"],"defaultLinkType":"default","connectivity":connectivity}
        with open(f"{self.path}/configs/config.json", 'w') as f: json.dump(config, f ,indent=4)
        #load configs
        self.prefix = "pipe"
        configs = self.getConfigs(False)
        #dummy
        if not "dummy.sh" in configs:
            dummyConfig = self.Templator.genDummy(id,connectivity)
            self.saveFile(dummyConfig,f"{self.path}/links/dummy.sh")
            self.setInterface("dummy","up")

    def findLowest(self,min,list):
        for i in range(min,min + 200):
            if i not in list and i % 2 == 0: return i

    def minimal(self,files,lastbyte=4,port=51820):
        ips,ports = [],[]
        for file in files:
            with open(f"{self.path}/links/{file}", 'r') as f: config = f.read()
            configPort = re.findall(f"listen-port\s([0-9]+)",config, re.MULTILINE)
            configIP = re.findall(f"ip address add dev.*?([0-9]+)\/",config, re.MULTILINE)
            if configPort:
                ports.append(int(configPort[0]))
                ips.append(int(configIP[0]))
        port = self.findLowest(port,ports)
        lastbyte = self.findLowest(lastbyte,ips)
        return lastbyte,port

    def getInterface(self,id,type="",network=""):
        return f"{self.prefix}{network}{id}{type}"

    def filterInterface(self,interface):
        return interface.replace(".sh","")

    def getInterfaceRemote(self,interface,network=""):
        serv = "" if "Serv" in interface else "Serv"
        v6 = "v6" if "v6" in interface else ""
        return f"{self.prefix}{network}{self.config['id']}{v6}{serv}"

    def setInterface(self,file,state):
        self.cmd(f'bash {self.path}/links/{file}.sh {state}')

    def cleanInterface(self,interface,deleteKey=True):
        os.remove(f"{self.path}/links/{interface}.sh")
        if deleteKey:
            os.remove(f"{self.path}/links/{interface}.key")
            if os.path.isfile(f"{self.path}/links/{interface}.pre"): os.remove(f"{self.path}/links/{interface}.pre")

    def saveFile(self,data,path):
        with open(path, 'w') as file: file.write(data)

    def getFilename(self,links,remote):
        for filename, row in links.items():
            if row['remote'] == remote: return filename

    def filesToLinks(self,files):
        links = {}
        for findex, filename in enumerate(files):
            if not filename.endswith(".sh") or filename == "dummy.sh": continue
            with open(f"{self.path}/links/{filename}", 'r') as file: config = file.read()
            #grab wg server ip from client wg config
            if "endpoint" in config:
                destination = re.findall(f'(10\.0\.[0-9]+\.)',config, re.MULTILINE)
                if not destination:
                    print(f"Ignoring {filename}")
                    continue
                destination = f"{destination[0]}1"
            elif "listen-port" in config:
                #grab ID from filename
                linkID = re.findall(f"pipe.*?([0-9]+)",filename, re.MULTILINE)[0]
                destination = f"10.0.{linkID}.1"
            #get remote endpoint
            local = re.findall(f'((10\.0\.[0-9]+\.)([0-9]+)\/31)',config, re.MULTILINE)[0]
            remote = f"{local[1]}{int(local[2])-1}" if self.sameNetwork(f"{local[1]}{int(local[2])-1}",local[0]) else f"{local[1]}{int(local[2])+1}"
            #grab publickey
            publicKey = re.findall(f"peer\s([A-Za-z0-9/.=+]+)",config,re.MULTILINE)[0]
            links[filename] = {"filename":filename,"vxlan":destination,"local":local[0],"remote":remote,'publicKey':publicKey}
        return links

    def AskProtocol(self,dest,token=""):
        #ask remote about available protocols
        req = self.call(f'{dest}/connectivity',{"token":token})
        if req == False: return False
        if req.status_code != 200:
            print("Failed to request connectivity info, maybe wrong version?")
            return False
        data = req.json()
        return data

    def connect(self,dest,token="",linkType=""):
        print(f"Connecting to {dest}")
        #generate new key pair
        clientPrivateKey, clientPublicKey = self.genKeys()
        #initial check
        configs = self.cmd('ip addr show')[0]
        links = re.findall(f"({self.prefix}[A-Za-z0-9]+): <POINTOPOINT.*?inet (10[0-9.]+\.[0-9]+)",configs, re.MULTILINE | re.DOTALL)
        isInitial = False if links else True
        #ask remote about available protocols
        data = self.AskProtocol(dest,token)
        if not data: return False
        #start with the protocol which is available
        if data['connectivity']['ipv4'] and self.config['connectivity']['ipv4']: isv6 = False
        elif data['connectivity']['ipv6'] and self.config['connectivity']['ipv6']: isv6 = True
        #if neither of these are available, leave it
        else: return False
        #linkType
        if linkType == "":
            if self.config['defaultLinkType'] in data['linkTypes']:
                linkType = self.config['defaultLinkType']
            else:
                linkType = "default"
        for run in range(2):
            #call destination
            req = self.call(f'{dest}/connect',{"clientPublicKey":clientPublicKey,"id":self.config['id'],"token":token,"ipv6":isv6,"initial":isInitial,"linkType":linkType})
            if req == False: return False
            if req.status_code == 200:
                resp = req.json()
                #check if v6 or v4
                interfaceID = f"{resp['id']}v6" if isv6 else resp['id']
                connectivity =  f"[{resp['connectivity']['ipv6']}]"  if isv6 else resp['connectivity']['ipv4']
                #interface
                interface = self.getInterface(interfaceID)
                #generate config
                clientConfig = self.Templator.genClient(interface,resp['id'],resp['lastbyte'],connectivity,resp['port'],resp['publicKeyServer'],linkType,resp['wgobfsSharedKey'])
                print(f"Creating & Starting {interface}")
                self.saveFile(clientPrivateKey,f"{self.path}/links/{interface}.key")
                self.saveFile(resp['preSharedKey'],f"{self.path}/links/{interface}.pre")
                self.saveFile(clientConfig,f"{self.path}/links/{interface}.sh")
                self.setInterface(interface,"up")
                #before we try to setup a v4 in v6 wg, we check if booth hosts have IPv6 connectivity
                if not self.config['connectivity']['ipv6'] or not resp['connectivity']['ipv6']: break
                if not self.config['connectivity']['ipv4'] or not resp['connectivity']['ipv4']: break
                #second run going to be IPv6 if available
                isv6 = True
            else:
                print(f"Failed to connect to {dest}")
                print(f"Got {req.text} as response")
                return False
        return True

    def updateServer(self,link,data):
        with open(f"{self.path}/links/{link}.sh", 'r') as file: config = file.read()
        config = re.sub(f"listen-port ([0-9]+)", f"listen-port {data['port']}", config, 0, re.MULTILINE)
        self.saveFile(config,f"{self.path}/links/{link}.sh")

    def updateClient(self,link,port):
        with open(f"{self.path}/links/{link}.sh", 'r') as file: config = file.read()
        parsed = re.findall(f"(endpoint.*?:)([0-9]+)",config, re.MULTILINE)
        oldEndPoint = ''.join(parsed[0])
        newEndPoint = f"{parsed[0][0]}{port}"
        config = re.sub(oldEndPoint, newEndPoint, config, 0, re.MULTILINE)
        self.saveFile(config,f"{self.path}/links/{link}.sh")

    def optimize(self,include=[]):
        links = self.getLinks()
        print("Checking Links")
        offline,online = self.checkLinks(links)
        combined = offline + online
        for link in combined:
            #if include given, ignore anything else not in the list
            if include and link not in include: continue
            #ignore v6 for now
            if "v6" in link or "Serv" in link: continue
            #prepare
            latency = {}
            data = links[link]
            print(f"Measuring {link}")
            fping = self.fping([data['remote']],5)
            before = self.getAvrg(fping[data['remote']])
            print(f"Current latency {before}ms")
            print(f"Checking {link}")
            #ask remote about available protocols
            dest = f'http://{data["vxlan"]}:8080'
            print(f'Calling {dest}/connectivity')
            resp = self.AskProtocol(f'{dest}','')
            if not resp: exit()
            #ignore v6 for now
            if not resp['connectivity']['ipv4']: continue
            #generate new key pair
            clientPrivateKey, clientPublicKey = self.genKeys()
            for port in range(1000,65000,2000):
                print(f"Testing on Port {port}")
                #setup link
                print(f'Calling {dest}/connect')
                req = self.call(f'{dest}/connect',{"clientPublicKey":clientPublicKey,"id":self.config['id'],"prefix":"172.16.","network":"Ping","basePort":port,"linkType":"default"})
                if req == False: 
                    print(f"Failed to setup Link for Port {port}, aborting")
                    continue
                if req.status_code != 200: 
                    print(f"Got {req.status_code} with {req.text} aborting")
                    continue
                resp = req.json()
                if resp['port'] != port: print(f"Switched from {port} to {resp['port']}")
                #prepare
                interfaceID = resp['id']
                connectivity = resp['connectivity']['ipv4']
                interface = self.getInterface(interfaceID,"v4","Ping")
                #generate config
                clientConfig = self.Templator.genClient(interface,resp['id'],resp['lastbyte'],connectivity,resp['port'],resp['publicKeyServer'],"default","","172.16.")
                #bring up the interface
                print(f"Creating & Starting {interface}")
                self.saveFile(clientPrivateKey,f"{self.path}/links/{interface}.key")
                self.saveFile(resp['preSharedKey'],f"{self.path}/links/{interface}.pre")
                self.saveFile(clientConfig,f"{self.path}/links/{interface}.sh")
                self.setInterface(interface,"up")
                #measure
                print("Measurement...")
                #Running fping
                targetIP = f"172.16.{resp['id']}.{resp['lastbyte']}"
                fping = self.fping([targetIP],4)
                if not fping: exit("Failed to ping target IP")
                #drop first ping result
                del fping[targetIP][0]
                avg = self.getAvrg(fping[targetIP])
                if avg == 65000: exit("Failed to parse ping results")
                latency[resp['port']] = avg
                print(f"Got {avg}ms")
                #terminate link
                interfaceRemote = self.getInterfaceRemote(interface,"Ping")
                print(f'Calling {dest}/disconnect')
                req = self.call(f'{dest}/disconnect',{"publicKeyServer":resp['publicKeyServer'],"interface":interfaceRemote,"wait":False})
                if req == False:
                    print("Failed to terminate link, unable to contact remote")
                    exit()
                if req.status_code == 200:
                    self.setInterface(interface,"down")
                    self.cleanInterface(interface)
                else:
                    print(f"Failed to terminate link, got {req.status_code} with {req.text} aborting")
                    exit()
            latency = sorted(latency.items(), key=lambda x: x[1])
            lowestPort = latency[0][0]
            diff = int(float(before) - float(latency[0][1]))
            if diff >= 10:
                print(f"Suggested Port {lowestPort} for a reduction of {diff}ms")
                print(f"Updating Remote Link {link}...")
                interfaceRemote = self.getInterfaceRemote(link)
                req = self.call(f'{dest}/update',{"publicKeyServer":data['publicKey'],"interface":interfaceRemote,"port":lowestPort},"PATCH")
                if req == False:
                    print("Failed to change remote port")
                    exit()
                if req.status_code == 200:
                    print(f"Updating Local Link {link}...")
                    interface = self.filterInterface(link)
                    self.setInterface(interface,"down")
                    self.updateClient(interface,lowestPort)
                    print("Waiting 20s before bringing the link back up")
                    time.sleep(20)
                    self.setInterface(interface,"up")
                    print(f"Measuring {link}")
                    fping = self.fping([data['remote']],5)
                    del fping[data['remote']][0]
                    after = self.getAvrg(fping[data['remote']])
                    print("--- Results ---")
                    print(f"Before {before}ms")
                    print(f"Now {after}ms")
                else:
                    print(f"Failed to change remote port, got {req.status_code} with {req.text} aborting")
                    exit()
            else:
                print("Nothing to optimize")

    def proximity(self):
        print("Getting Routes")
        routes = self.cmd("birdc show route")[0]
        targets = re.findall(f"(10\.0\.[0-9]+\.0\/30)",routes, re.MULTILINE)
        configs = self.cmd('ip addr show')[0]
        links = re.findall(f"({self.prefix}[A-Za-z0-9]+): <POINTOPOINT.*?inet (10[0-9.]+\.[0-9]+)",configs, re.MULTILINE | re.DOTALL)
        print("Getting Connection info")
        ips = {}
        for target in targets:
            target = target.replace("0/30","1")
            resp = self.AskProtocol(f'http://{target}:8080','')
            if not resp: continue
            ips[resp['connectivity']['ipv4']] = target
            ips[resp['connectivity']['ipv6']] = target
        existing = []
        for ip in list(targets):
            for link in links:
                if self.resolve(link[1],ip.replace("/30",""),24):
                    #multiple links in the same subnet
                    if ip in targets: existing.append(ip.replace("0/30","1"))
        fpingTargets = []
        for ip in ips:
            if ip != None: fpingTargets.append(ip)
        print("Getting Latency")
        fping = self.fping(fpingTargets)
        latencyData = {}
        print("Parsing Results")
        for ip in fping: latencyData[ip] = self.getAvrg(fping[ip])
        latencyData = {k: latencyData[k] for k in sorted(latencyData, key=latencyData.get)}
        result = []
        result.append("Target\tIP address\tConnected\tLatency")
        result.append("-------\t-------\t-------\t-------")
        for ip,latency in latencyData.items(): result.append(f"{ips[ip]}\t{ip}\t{bool(ips[ip] in existing)}\t{latency}ms")
        result = self.formatTable(result)
        print(result)

    def getLinks(self):
        print("Getting Links")
        files = os.listdir(f"{self.path}/links/")
        links = self.filesToLinks(files)
        if not links: exit("No links found.")
        return links

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

    def disconnect(self,force=False,link=""):
        links = self.getLinks()
        print("Checking Links")
        offline,online = self.checkLinks(links)
        #shutdown the links that are offline first
        if offline: print(f"Found offline links, disconnecting them first. {offline}")
        targets = offline + online
        print("Disconnecting")
        for filename in targets:
            #if a specific link is given filter out
            if link and link not in filename: continue
            interfaceRemote = self.getInterfaceRemote(filename)
            #call destination
            data = links[filename]
            print(f'Calling http://{data["vxlan"]}:8080/disconnect')
            req = self.call(f'http://{data["vxlan"]}:8080/disconnect',{"publicKeyServer":data['publicKey'],"interface":interfaceRemote})
            if req == False and force == False: continue
            if force or req.status_code == 200:
                interface = self.filterInterface(filename)
                self.setInterface(interface,"down")
                self.cleanInterface(interface)
            else:
                print(f"Got {req.status_code} with {req.text} aborting")
        #load configs
        configs = self.getConfigs(False)
        #get all links
        files = os.listdir(f"{self.path}/links/")
        #check for dummy and .gitignore
        if "dummy.sh" in files: files.remove("dummy.sh")
        if ".gitignore" in files: files.remove(".gitignore")
        #clear state.json if no links left
        if os.path.isfile(f"{self.path}/configs/state.json") and not files:
             os.remove(f"{self.path}/configs/state.json")