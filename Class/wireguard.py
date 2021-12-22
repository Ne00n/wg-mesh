from Class.templator import Templator
import urllib.request, json, re, os
from Class.base import Base

class Wireguard(Base):
    path = os.path.dirname(os.path.realpath(__file__))
    Templator = Templator()
    prefix = "pipe"

    def genKeys(self):
        keys = self.cmd('key=$(wg genkey) && echo $key && echo $key | wg pubkey')
        privateKeyServer, publicKeyServer = keys.splitlines()
        return privateKeyServer, publicKeyServer

    def init(self,name,id):
        if os.path.isfile(f"{self.path}/config.json"): exit("Config already exists")
        print("Getting external IPv4")
        request = urllib.request.urlopen("https://checkip.amazonaws.com", timeout=3)
        if (request.getcode() != 200): exit("Failed to get external IPv4")
        ipv4 = request.read().decode('utf-8').strip()
        print(f"Got {ipv4} as IPv4")
        print("Generating config.json")
        config = {"name":name,"id":id,"ipv4":ipv4}
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

        if not os.path.isdir('/etc/wireguard/'): exit("Wireguard directory not found, not installed?")
        configs = self.cmd('ls /etc/wireguard/')
        parsed = re.findall(f"^{self.prefix}[A-Za-z0-9]+",configs, re.MULTILINE)
        if f"{self.prefix}{name}" in parsed: exit("Wireguard config already exists with same name")

        ip,port = self.minimal(parsed)

        print("Generating Wireguard keypair")
        privateKeyServer, publicKeyServer = self.genKeys()
        privateKeyClient, publicKeyClient = self.genKeys()
        serverConfig = self.Templator.genServer(config['id'],ip,port,privateKeyServer,publicKeyClient)
        cientConfig = self.Templator.genClient(config['id'],ip,config['ipv4'],port,privateKeyClient,publicKeyServer)
        print(f'Creating & Starting {name} on {config["name"]}')
        file = f'{self.prefix}{name}Serv'
        self.cmd(f'echo "{serverConfig}" > /etc/wireguard/{file}.conf && systemctl enable wg-quick@{file} && systemctl start wg-quick@{file}')
        print(f'Run this on {name} to connect to {config["name"]}')
        print(f'curl -so- https://raw.githubusercontent.com/Ne00n/wg-mesh/master/install.sh | bash -s -- connect {config["name"]} {config["id"]} {ip} {config["ipv4"]} {port} {privateKeyClient} {publicKeyServer}')

    def connect(self,data):
        print('Generating client config')
        cientConfig = self.Templator.genClient(data[1],data[2],data[3],data[4],data[5],data[6])
        print(f'Creating & Starting {data[0]}')
        config = f'{self.prefix}{data[0]}'
        self.cmd(f'echo "{cientConfig}" > /etc/wireguard/{config}.conf && systemctl enable wg-quick@{config} && systemctl start wg-quick@{config}')
        ping = self.cmd(f'fping 10.0.{data[1]}.{data[2]}')
        if "alive" in ping:
            print("Connected, Link is up")
        else:
            print("Link not pingable, something went wrong")
