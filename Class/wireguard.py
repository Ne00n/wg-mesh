from Class.templator import Templator
import subprocess, re, os

class Wireguard:
    prefix = "pipe"

    def cmd(self,command):
        p = subprocess.run(f"{command}", stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        return p.stdout.decode('utf-8')

    def join(self,name):
        T = Templator()
        if not os.path.isdir('/etc/wireguard/'): exit("Wireguard directory not found, not installed?")
        configs = self.cmd('ls /etc/wireguard/')
        parsed = re.findall(f"^{self.prefix}[A-Za-z0-9]+",configs, re.MULTILINE)
        if f"{self.prefix}{name}" in parsed: exit("Config already exists with same name")
        print("Generating Wireguard keypair")
        keys = self.cmd('key=$(wg genkey) && echo $key && echo $key | wg pubkey')
        privateKeyServer, publicKeyServer = keys.splitlines()
        keys = self.cmd('key=$(wg genkey) && echo $key && echo $key | wg pubkey')
        privateKeyClient, publicKeyClient = keys.splitlines()
        serverConfig = T.genServer(1,1,51820,privateKeyServer,publicKeyClient)
        print(serverConfig)
        cientConfig = T.genClient(1,1,"1.1.1.1",51820,privateKeyClient,publicKeyServer)
        print(cientConfig)