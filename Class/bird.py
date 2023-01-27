import netaddr, random, time, json, re, os
from Class.templator import Templator
from Class.wireguard import Wireguard
from Class.base import Base

class Bird(Base):
    Templator = Templator()
    prefix = "pipe"

    def __init__(self,path):
        self.path = path

    def resolve(self,ip,range,netmask):
        rangeDecimal = int(netaddr.IPAddress(range))
        ipDecimal = int(netaddr.IPAddress(ip))
        wildcardDecimal = pow( 2, ( 32 - int(netmask) ) ) - 1
        netmaskDecimal = ~ wildcardDecimal
        return ( ( ipDecimal & netmaskDecimal ) == ( rangeDecimal & netmaskDecimal ) );

    def getAvrg(self,row):
        result = 0
        for entry in row: result += float(entry[0])
        return int(float(result / len(row)) * 100)
    
    def genTargets(self,links):
        result = {}
        for link in links:
            nic,ip,lastByte = link[0],link[2],link[3]
            origin = ip+lastByte
            #Client or Server roll the dice or rather not, so we ping the correct ip
            target = self.resolve(f"{ip}{int(lastByte)+1}",origin,31)
            if target == True:
                targetIP = f"{ip}{int(lastByte)+1}"
            else:
                targetIP = f"{ip}{int(lastByte)-1}"
            result[nic] = {"target":targetIP,"origin":origin}
        return result

    def getLatency(self,targets):
        fping = "fping -c 7"
        for nic,data in targets.items():
            fping += f" {data['target']}"
        result = self.cmd(fping)
        parsed = re.findall("([0-9.]+).*?([0-9]+.[0-9]).*?([0-9])% loss",result, re.MULTILINE)
        if not parsed: 
            print("No pingable links found.")
            return False
        latency =  {}
        for ip,ms,loss in parsed:
            if ip not in latency:
                latency[ip] = []
            latency[ip].append([ms,loss])
        for entry,row in latency.items():
            row = row[2:] #drop the first 2 pings
            row.sort()
        for nic,data in list(targets.items()):
            for entry,row in latency.items():
                if entry == data['target']:
                    if len(row) < 5: print("Warning, expected 5 pings, got",len(row),"from",data['target'],"possible Packetloss")
                    data['latency'] = self.getAvrg(row)
                elif data['target'] not in latency and nic in targets:
                    print("Warning: cannot reach",data['target'],"skipping")
                    del targets[nic]
        if (len(targets) != len(latency)):
            print("Warning: Targets do not match expected responses.")
        return targets

    def bird(self):
        print("Collecting Network data")
        configs = self.cmd('ip addr show')
        links = re.findall(f"(({self.prefix})[A-Za-z0-9]+): <POINTOPOINT.*?inet (10[0-9.]+\.)([0-9]+)",configs, re.MULTILINE | re.DOTALL)
        local = re.findall("inet (10\.0\.(?!252)[0-9.]+\.1)\/(32|30) scope global lo",configs, re.MULTILINE | re.DOTALL)
        if not links: 
            print("No wireguard interfaces found") 
            return False
        print("Getting Network targets")
        nodes = self.genTargets(links)
        print("Latency messurement")
        latencyData = self.getLatency(nodes)
        if not latencyData: return False
        print("Generating config")
        bird = self.Templator.genBird(latencyData,local,int(time.time()))
        if bird == "": 
            print("No bird config generated")
            return False
        print("Writing config")
        self.cmd(f"echo '{bird}' > /etc/bird/bird.conf")
        print("Reloading bird")
        self.cmd("sudo systemctl reload bird")

    def mesh(self):
        configs = self.cmd('ip addr show')
        links = re.findall(f"({self.prefix}[A-Za-z0-9]+): <POINTOPOINT.*?inet (10[0-9.]+\.[0-9]+)",configs, re.MULTILINE | re.DOTALL)
        local = re.findall("inet (10\.0\.(?!252)[0-9.]+\.1)\/30 scope global lo",configs, re.MULTILINE | re.DOTALL)
        if not links or not local: 
            print("No wireguard interfaces found") 
            return False
        proc = self.cmd("pgrep bird")
        if proc == "": 
            print("bird not running")
            return False
        time.sleep(10)
        routes = self.cmd("birdc show route")
        targets = re.findall(f"((10\.0\.[0-9]+\.0)\/30)",routes, re.MULTILINE)
        if not targets: 
            print("bird returned no routes, did you setup bird?")
            return False
        #vxlan fuckn magic
        vxlan = self.cmd("bridge fdb show dev vxlan1 | grep dst")
        for target in targets:
            ip = target[0].replace("0/30","1")
            if not ip in vxlan: self.cmd(f"sudo bridge fdb append 00:00:00:00:00:00 dev vxlan1 dst {ip}")
        #remove local machine from list
        for ip in list(targets):
            if self.resolve(local[0],ip[1],30):
                targets.remove(ip)
        #run against existing links
        for ip in list(targets):
            for link in links:
                if self.resolve(link[1],ip[1],24):
                    #multiple links in the same subnet
                    if ip in targets: targets.remove(ip)
        #run against local link names
        for ip in list(targets):
            for link in links:
                splitted = ip[1].split(".")
                if f"pipe{splitted[2]}" in link[0]:
                    #multiple links in the same subnet
                    if ip in targets: targets.remove(ip)
        print("Possible targets",targets)
        #keep waiting for targets if empty
        if not targets: return False
        #To prevent creating connections to new nodes joined afterwards, save state
        if os.path.isfile(f"{self.path}/configs/state.json"):
            print("state.json already exist, skipping")
        else:
            #wireguard
            wg = Wireguard(self.path)
            config = wg.getConfig()
            print("meshing™")
            results = {}
            for target in targets:
                targetSplit = target[0].split(".")
                #reserve 10.0.240+ for clients, don't mesh
                if int(targetSplit[2]) >= 240: continue
                dest = target[0].replace(".0/30",".1")
                #no token needed but external IP for the client
                resp = wg.connect(dest,"",config['connectivity']['ipv4'])
                if resp:
                    results[target] = True
                else:
                    results[target] = False
            print("saving state.json")
            with open(f"{self.path}/configs/state.json", 'w') as f: json.dump(results, f ,indent=4)