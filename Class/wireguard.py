from Class.templator import Templator
import urllib.request, requests, random, string, json, time, re, os
from Class.base import Base

class Wireguard(Base):
    Templator = Templator()
    prefix = "pipe"

    def __init__(self,path,skip=False):
        self.path = path
        if skip: return
        if not os.path.isfile(f"{self.path}/configs/config.json"): exit("Config missing")
        with open(f'{self.path}/configs/config.json') as f: self.config = json.load(f)

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

    def hasDummy(self,configs):
        for file in configs:
            if "dummy.sh" == file: return True
        return False
        
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

    def init(self,name,id):
        if os.path.isfile(f"{self.path}/config.json"): exit("Config already exists")
        print("Getting external IPv4 and IPv6")
        ipv4 = self.fetch("https://checkip.amazonaws.com")
        ipv6 = self.fetch("https://api6.ipify.org/")
        print(f"Got {ipv4} and {ipv6}")

        print("Generating config.json")
        config = {"name":name,"id":id,"connectivity":{"ipv4":ipv4,"ipv6":ipv6}}
        with open(f"{self.path}/configs/config.json", 'w') as f: json.dump(config, f ,indent=4)

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

    def filterInterfaceRemote(self,interface):
        return interface.replace(".sh","").replace("Serv","")

    def setInterface(self,file,state):
        self.cmd(f'bash {self.path}/links/{file}.sh {state}')

    def cleanInterface(self,interface,deleteKey=True):
        os.remove(f"{self.path}/links/{interface}.sh")
        if deleteKey:
            os.remove(f"{self.path}/links/{interface}.key")

    def saveFile(self,data,path):
        with open(path, 'w') as file: file.write(data)

    def error(self,run):
        print(f"Retrying {run+1} of 4")
        if run == 3:
            print("Aborting, limit reached.")
            return False
        time.sleep(2)
        return True

    def connect(self,dest,token="",external=""):
        print(f"Connecting to {dest}")
        privateKeyServer, publicKeyServer = self.genKeys()
        configs = self.getConfigs(False)
        lastbyte,port = self.minimal(configs)
        #call destination
        for run in range(4):
            try:
                req = requests.post(f'http://{dest}:8080/connect', json={"publicKeyServer":publicKeyServer,"id":self.config['id'],"lastbyte":lastbyte,"port":port,"token":token,"external":external})
                if req.status_code == 200: break
                print(f"Got {req.text} as response")
                resp = self.error(run)
                if not resp: return False
            except Exception as ex:
                print(f"Error {ex}")
                resp = self.error(run)
                if not resp: return False
        if req.status_code == 200:
            print("Got 200")
            resp = req.json()
            interface = self.getInterface(resp['id'],"Serv")
            serverConfig = self.Templator.genServer(interface,dest,self.config['id'],lastbyte,port,resp['clientPublicKey'])
            print(f"Creating & Starting {interface}")
            self.saveFile(privateKeyServer,f"{self.path}/links/{interface}.key")
            self.saveFile(serverConfig,f"{self.path}/links/{interface}.sh")
            self.setInterface(interface,"up")
            #load configs
            configs = self.getConfigs()
            #check for dummy
            if not self.hasDummy(configs):
                dummyConfig = self.Templator.genDummy(self.config['id'])
                self.saveFile(dummyConfig,f"{self.path}/links/dummy.sh")
                self.setInterface("dummy","up")
            return True
        else:
            print(f"Failed to connect to {dest}")
            print(f"Got {req.text} as response")

    def disconnect(self):
        print("Disconnecting")
        files = os.listdir(f"{self.path}/links/")
        for findex, filename in enumerate(files):
            if filename == "dummy.sh": continue
            if not filename.endswith(".sh"): continue
            print(f"Reading Link {filename}")
            with open(f"{self.path}/links/{filename}", 'r') as file: config = file.read()
            if "endpoint" in config:
                destination = re.findall(f"endpoint\s([0-9.]+)",config, re.MULTILINE)
            elif "listen-port" in config:
                destination = re.findall(f"client\s([0-9.]+)",config, re.MULTILINE)
            publicKeyServer = re.findall(f"peer\s([A-Za-z0-9/.=+]+)",config,re.MULTILINE)
            interface = self.filterInterfaceRemote(filename)
            #call destination
            try:
                req = requests.post(f'http://{destination[0]}:8080/disconnect', json={"publicKeyServer":publicKeyServer[0],"interface":interface})
                if req.status_code == 200:
                    interface = self.filterInterface(filename)
                    self.setInterface(interface,"down")
                    self.cleanInterface(interface)
                else:
                    print(f"Got {req.status_code} with {req.text} aborting")
            except Exception as ex:
                exit(ex)
        #load configs
        configs = self.getConfigs()
        #check for dummy
        if not self.hasDummy(configs):
            #clean dummy
            self.setInterface("dummy","down")
            self.cleanInterface("dummy",False)