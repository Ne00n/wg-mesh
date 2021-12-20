from Class.templator import Templator
import subprocess, urllib.request, json, re, os

class Wireguard:
    path = os.path.dirname(os.path.realpath(__file__))
    prefix = "pipe"

    def cmd(self,command):
        p = subprocess.run(f"{command}", stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        return p.stdout.decode('utf-8')

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

    def minimal(self,files,ip=1,port=51820):
        return ip,port

    def join(self,name):
        T = Templator()

        if not os.path.isfile(f"{self.path}/config.json"): exit("Config missing")
        with open(f'{self.path}/config.json') as f: config = json.load(f)

        if not os.path.isdir('/etc/wireguard/'): exit("Wireguard directory not found, not installed?")
        configs = self.cmd('ls /etc/wireguard/')
        parsed = re.findall(f"^{self.prefix}[A-Za-z0-9]+",configs, re.MULTILINE)
        if f"{self.prefix}{name}" in parsed: exit("Wireguard config already exists with same name")

        ip,port = self.minimal(parsed)

        print("Generating Wireguard keypair")
        keys = self.cmd('key=$(wg genkey) && echo $key && echo $key | wg pubkey')
        privateKeyServer, publicKeyServer = keys.splitlines()
        keys = self.cmd('key=$(wg genkey) && echo $key && echo $key | wg pubkey')
        privateKeyClient, publicKeyClient = keys.splitlines()
        serverConfig = T.genServer(config['id'],ip,port,privateKeyServer,publicKeyClient)
        print(serverConfig)
        cientConfig = T.genClient(config['id'],ip,config['ipv4'],port,privateKeyClient,publicKeyServer)
        print(cientConfig)