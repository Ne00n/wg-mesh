from Class.templator import Templator
import urllib.request, requests, random, string, json, re, os
from Class.base import Base

class Wireguard(Base):
    path = os.path.dirname(os.path.realpath(__file__)).replace("Class","configs")
    folder = "/opt/wg-mesh/"
    Templator = Templator()
    prefix = "pipe"

    def __init__(self,skip=False):
        if skip: return
        if not os.path.isfile(f"{self.path}/config.json"): exit("Config missing")
        with open(f'{self.path}/config.json') as f: self.config = json.load(f)

    def genKeys(self):
        keys = self.cmd('key=$(wg genkey) && echo $key && echo $key | wg pubkey')
        privateKeyServer, publicKeyServer = keys.splitlines()
        return privateKeyServer, publicKeyServer

    def loadConfigs(self,abort=True):
        if not os.path.isdir('/etc/wireguard/'): exit("Wireguard directory not found, not installed?")
        files = self.cmd('ls /etc/wireguard/')
        configs = re.findall(f"^{self.prefix}[A-Za-z0-9]+",files, re.MULTILINE)
        if not configs and abort: exit(f"No {self.prefix} configs found")
        return configs

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
        with open(f"{self.path}/config.json", 'w') as f: json.dump(config, f ,indent=4)

    def findLowest(self,min,list):
        for i in range(min,min + 200):
            if i not in list and i % 2 == 0: return i

    def minimal(self,files,ip=4,port=51820):
        ips,ports = [],[]
        for file in files:
            with open(f"/etc/wireguard/{file}.conf", 'r') as f: config = f.read()
            configPort = re.findall(f"^Endpoint = .*?:([0-9]+)",config, re.MULTILINE)
            configIP = re.findall(f"^Address =.*?([0-9]+)\/",config, re.MULTILINE)
            if configPort:
                ports.append(int(configPort[0]))
                ips.append(int(configIP[0]))
        port = self.findLowest(port,ports)
        ip = self.findLowest(ip,ips)
        return ip,port

    def getInterface(self,id,type=""):
        return f"{self.prefix}{id}{type}"

    def saveConfig(self,config,file):
        self.saveFile(config,f"/opt/wg-mesh/links/{file}.sh")
        self.cmd(f'bash /opt/wg-mesh/links/{file}.sh up')

    def saveFile(self,data,path):
        with open(path, 'w') as file:
            file.write(data)

    def connect(self,dest):
        print(f"Connecting to {dest}")
        privateKeyServer, publicKeyServer = self.genKeys()
        configs = self.loadConfigs(False)
        ip,port = self.minimal(configs)
        #call destination
        try:
            req = requests.post(f'http://{dest}:8080/connect', json={"publicKeyServer":publicKeyServer,"id":self.config['id'],"ip":ip,"port":port})
        except Exception as ex:
            exit(ex)
        if req.status_code == 200:
            print("Got 200")
            resp = req.json()
            print(f"clientPublicKey {resp['clientPublicKey']}")
            resp = req.json()
            interface = self.getInterface(resp['id'],"Serv")
            serverConfig = self.Templator.genServer(interface,dest,self.config['id'],ip,port,resp['clientPublicKey'])
            print(f"Creating & Starting {interface}")
            self.saveFile(privateKeyServer,f"/opt/wg-mesh/links/{interface}.key")
            self.saveConfig(serverConfig,interface)
        else:
            print(f"Failed to connect to {ip}")

    def disconnect(self):
        print("Disconnecting")
        files = os.listdir(f"{self.folder}links/")
        for findex, filename in enumerate(files):
            if not filename.endswith(".sh"): continue
            with open(f"{self.folder}links/{filename}", 'r') as file:
                config = file.read()
            if "endpoint" in config:
                destination = re.findall(f"endpoint\s([0-9.]+)",config, re.MULTILINE)
            elif "listen-port" in config:
                destination = re.findall(f"client\s([0-9.]+)",config, re.MULTILINE)
            publicKeyServer = re.findall(f"peer\s([A-Za-z0-9/.=]+)",config,re.MULTILINE)
            interface = filename.replace(".sh","")
            #call destination
            try:
                req = requests.post(f'http://{destination[0]}:8080/disconnect', json={"publicKeyServer":publicKeyServer[0],"interface":interface})
                if req.status_code == 200:
                    self.cmd(f'bash /opt/wg-mesh/links/{filename}.sh')
                    os.remove(f"/opt/wg-mesh/links/{filename}.sh")
            except Exception as ex:
                exit(ex)

    def mesh(self):
        proc = self.cmd("pgrep bird")
        if proc == "": exit("bird not running")
        routes = self.cmd("birdc show route")
        ips = re.findall(f"\[[0-9.]+\]",routes, re.MULTILINE)
        if not ips: exit("bird returned no routes, did you setup bird?")
        configs = self.loadConfigs()