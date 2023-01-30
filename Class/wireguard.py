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

    def genKeys(self):
        keys = self.cmd('key=$(wg genkey) && echo $key && echo $key | wg pubkey')
        privateKeyServer, publicKeyServer = keys.splitlines()
        return privateKeyServer, publicKeyServer

    def getConfig(self):
        return self.config

    def getPublic(self,private):
        return self.cmd(f'echo {private} | wg pubkey').rstrip()

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
        
    def getEndpoints(self,configs):
        ips = []
        for config in configs:
            data = re.findall(f"(10\.0\.[0-9]+).",config, re.MULTILINE)
            ips.append(f"{data[0]}.1")
        ips = list(set(ips))
        return ips

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
        config = {"listen":listen,"prefix":"pipe","id":id,"connectivity":{"ipv4":ipv4,"ipv6":ipv6}}
        with open(f"{self.path}/configs/config.json", 'w') as f: json.dump(config, f ,indent=4)
        #load configs
        self.prefix = "pipe"
        configs = self.getConfigs(False)
        #dummy
        if not "dummy.sh" in configs:
            dummyConfig = self.Templator.genDummy(id)
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

    def getInterface(self,id,type=""):
        return f"{self.prefix}{id}{type}"

    def pingIP(self,ip):
        self.cmd(f"fping -c3 {ip}")

    def filterInterface(self,interface):
        return interface.replace(".sh","")

    def getInterfaceRemote(self,interface):
        serv = "" if "Serv" in interface else "Serv"
        v6 = "v6" if "v6" in interface else ""
        return f"{self.prefix}{self.config['id']}{v6}{serv}"

    def setInterface(self,file,state):
        self.cmd(f'bash {self.path}/links/{file}.sh {state}')

    def cleanInterface(self,interface,deleteKey=True):
        os.remove(f"{self.path}/links/{interface}.sh")
        if deleteKey:
            os.remove(f"{self.path}/links/{interface}.key")

    def saveFile(self,data,path):
        with open(path, 'w') as file: file.write(data)

    def connect(self,dest,token=""):
        #check if we got v6 here
        if ":" in dest and not "[" in dest: dest = f"[{dest}]"
        print(f"Connecting to {dest}")
        #generate new key pair
        clientPrivateKey, clientPublicKey = self.genKeys()
        for run in range(2):
            #call destination
            isv6 = True if run == 0 and ":" in dest or run == 1 and not ":" in dest else False
            req = self.call(f'http://{dest}:8080/connect',{"clientPublicKey":clientPublicKey,"id":self.config['id'],"token":token,"ipv6":isv6})
            if req == False: return False
            if req.status_code == 200:
                resp = req.json()
                #check if v6 or v4
                interfaceID = f"{resp['id']}v6" if isv6 else resp['id']
                connectivity = resp['connectivity']['ipv6'] if isv6 else resp['connectivity']['ipv4']
                #interface
                interface = self.getInterface(interfaceID)
                #generate config
                clientConfig = self.Templator.genClient(interface,resp['id'],resp['lastbyte'],connectivity,resp['port'],resp['publicKeyServer'])
                print(f"Creating & Starting {interface}")
                self.saveFile(clientPrivateKey,f"{self.path}/links/{interface}.key")
                self.saveFile(clientConfig,f"{self.path}/links/{interface}.sh")
                self.setInterface(interface,"up")
                #before we try to setup a v4 in v6 wg, we check if booth hosts have IPv6 connectivity
                if not self.config['connectivity']['ipv6'] or not resp['connectivity']['ipv6']: break
                if not self.config['connectivity']['ipv4'] or not resp['connectivity']['ipv4']: break
            else:
                print(f"Failed to connect to {dest}")
                print(f"Got {req.text} as response")
                return False
        return True

    def disconnect(self,force=False,link=""):
        print("Disconnecting")
        files = os.listdir(f"{self.path}/links/")
        for findex, filename in enumerate(files):
            if filename == "dummy.sh": continue
            if not filename.endswith(".sh"): continue
            #if a specific link is given filter out
            if link and link not in filename: continue
            print(f"Reading Link {filename}")
            with open(f"{self.path}/links/{filename}", 'r') as file: config = file.read()
            #grab wg server ip from client wg config
            if "endpoint" in config:
                destination = re.findall(f"endpoint\s([0-9a-z:.]+):",config, re.MULTILINE)[0]
            elif "listen-port" in config:
                destination = re.findall(f"client\s([0-9a-z:.]+)",config, re.MULTILINE)[0]
            #check if we got v6 here
            if ":" in destination: destination = f"[{destination}]"
            publicKeyServer = re.findall(f"peer\s([A-Za-z0-9/.=+]+)",config,re.MULTILINE)
            interfaceRemote = self.getInterfaceRemote(filename)
            #call destination
            req = self.call(f'http://{destination}:8080/disconnect',{"publicKeyServer":publicKeyServer[0],"interface":interfaceRemote})
            if req == False and force == False: continue
            if force or req.status_code == 200:
                interface = self.filterInterface(filename)
                self.setInterface(interface,"down")
                self.cleanInterface(interface)
            else:
                print(f"Got {req.status_code} with {req.text} aborting")
        #load configs
        configs = self.getConfigs(False)
        #check for dummy
        if "dummy.sh" in configs:
            #clean dummy
            self.setInterface("dummy","down")
            self.cleanInterface("dummy",False)
        #get all links
        files = os.listdir(f"{self.path}/links/")
        #clear state.json if no links left
        if os.path.isfile(f"{self.path}/configs/state.json") and not files:
             os.remove(f"{self.path}/configs/state.json")