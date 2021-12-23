from Class.templator import Templator
import urllib.request, json, re, os
from Class.base import Base

class Wireguard(Base):
    path = os.path.dirname(os.path.realpath(__file__)).replace("Class","configs")
    Templator = Templator()
    prefix = "pipe"

    def genKeys(self):
        keys = self.cmd('key=$(wg genkey) && echo $key && echo $key | wg pubkey')
        privateKeyServer, publicKeyServer = keys.splitlines()
        return privateKeyServer, publicKeyServer

    def loadConfigs(self):
        if not os.path.isdir('/etc/wireguard/'): exit("Wireguard directory not found, not installed?")
        configs = self.cmd('ls /etc/wireguard/')
        return re.findall(f"^{self.prefix}[A-Za-z0-9]+",configs, re.MULTILINE)

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
        with open(f"{self.path}/config.json", 'w') as f: json.dump(config, f)
        print("Setting up wireguard dummy for xlan,forwarding...")
        privateKeyServer, publicKeyServer = self.genKeys()
        config = self.Templator.genDummy(id,privateKeyServer)
        self.cmd(f'echo "{config}" > /etc/wireguard/dummy.conf && systemctl enable wg-quick@dummy && systemctl start wg-quick@dummy')

    def minimal(self,files,ip=4,port=51820):
        ips,ports = [],[]
        for file in files:
            with open(f"/etc/wireguard/{file}.conf", 'r') as f: config = f.read()
            configPort = re.findall(f"^Endpoint = .*?:([0-9]+)",config, re.MULTILINE)
            configIP = re.findall(f"^Address =.*?([0-9]+)\/",config, re.MULTILINE)
            if configPort:
                ports.append(int(configPort[0]))
                ips.append(int(configIP[0]))
        for i in range(port, port + 200): 
            if i not in ports: 
                port = i
                break
        for i in range(ip,ip + 200):
            if i not in ips and i % 2 == 0:
                ip = i
                break
        return ip,port

    def join(self,name):
        if not os.path.isfile(f"{self.path}/config.json"): exit("Config missing")
        with open(f'{self.path}/config.json') as f: config = json.load(f)

        configs = self.loadConfigs()
        if f"{self.prefix}{name}" in configs: exit("Wireguard config already exists with same name")
        ip,port = self.minimal(configs)

        print("Generating Wireguard keypair")
        privateKeyServer, publicKeyServer = self.genKeys()
        privateKeyClient, publicKeyClient = self.genKeys()
        serverConfig = self.Templator.genServer(config['id'],ip,port,privateKeyServer,publicKeyClient)
        #cientConfig = self.Templator.genClient(config['id'],ip,config['ipv4'],port,privateKeyClient,publicKeyServer)
        print(f'Creating & Starting {name} on {config["name"]}')
        externalIP = self.getIP(config)
        suffix = 'v6' if ":" in externalIP else ""
        file = f'{self.prefix}{name}{suffix}Serv'
        self.cmd(f'echo "{serverConfig}" > /etc/wireguard/{file}.conf && systemctl enable wg-quick@{file} && systemctl start wg-quick@{file}')
        print(f'Run this on {name} to connect to {config["name"]}')
        print(f'curl -so- https://raw.githubusercontent.com/Ne00n/wg-mesh/master/install.sh | bash -s -- connect {config["name"]} {config["id"]} {ip} {externalIP} {port} {privateKeyClient} {publicKeyServer}')

    def connect(self,name,id,vpnIP,externalIP,port,privateKeyClient,publicKeyServer):
        print('Generating client config')
        if ":" in externalIP:
            ip,suffix = f'[{externalIP}]',"v6"
        else:
            ip,suffix = externalIP,""
        cientConfig = self.Templator.genClient(id,vpnIP,ip,port,privateKeyClient,publicKeyServer)
        print(f'Creating & Starting {name}')
        config = f'{self.prefix}{name}{suffix}'
        self.cmd(f'echo "{cientConfig}" > /etc/wireguard/{config}.conf && systemctl enable wg-quick@{config} && systemctl start wg-quick@{config}')
        ping = self.cmd(f'fping 10.0.{id}.{vpnIP}')
        if "alive" in ping:
            print("Connected, Link is up")
        else:
            print("Link not pingable, something went wrong")

    def shutdown(self):
        configs = self.loadConfigs()
        print(f'Shutting down dummy')
        self.cmd(f'systemctl stop wg-quick@dummy')
        if not configs: exit(f"No {self.prefix} configs found")
        for config in configs:
            print(f'Shutting down {config}')
            self.cmd(f'systemctl stop wg-quick@{config}')

    def startup(self):
        configs = self.loadConfigs()
        print(f'Starting dummy')
        self.cmd(f'systemctl start wg-quick@dummy')
        if not configs: exit(f"No {self.prefix} configs found")
        for config in configs:
            print(f'Starting {config}')
            self.cmd(f'systemctl start wg-quick@{config}')

    def clean(self):
        configs = self.loadConfigs()
        if not configs: exit(f"No {self.prefix} configs found")
        for config in configs:
            print(f'Shutting down {config}')
            self.cmd(f'systemctl stop wg-quick@{config}')
            print(f'Deleting {config}')
            os.remove(f"/etc/wireguard/{config}.conf")