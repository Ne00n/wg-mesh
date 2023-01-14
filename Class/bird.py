import netaddr, random, time, json, re
from Class.templator import Templator
from Class.base import Base

class Bird(Base):
    Templator = Templator()
    prefix = "pipe"

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
        if not parsed: exit("No pingable link found")
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
        if not links: exit("No wireguard interfaces found")
        print("Getting Network targets")
        nodes = self.genTargets(links)
        print("Latency messurement")
        latencyData = self.getLatency(nodes)
        print("Generating config")
        bird = self.Templator.genBird(latencyData,local,int(time.time()))
        if bird == "": exit("No bird config generated")
        print("Writing config")
        self.cmd(f'echo "{bird}" > /etc/bird/bird.conf')
        proc = self.cmd("pgrep bird")
        if proc == "":
            print("Starting bird")
            self.cmd("service bird start")
        else:
            print("Reloading bird")
            self.cmd("service bird reload")

    def mesh(self):
        proc = self.cmd("pgrep bird")
        if proc == "": exit("bird not running")
        routes = self.cmd("birdc show route")
        ips = re.findall(f"\[[0-9.]+\]",routes, re.MULTILINE)
        if not ips: exit("bird returned no routes, did you setup bird?")
        configs = self.loadConfigs()