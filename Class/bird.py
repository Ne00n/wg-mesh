import random, time, json, re, os
from Class.templator import Templator
from Class.wireguard import Wireguard
from Class.network import Network
from Class.base import Base

class Bird(Base):
    Templator = Templator()

    def __init__(self,path,logger):
        super().__init__() 
        self.config = self.readFile(f'{path}/configs/config.json')
        self.prefix = self.config['prefix']
        self.Network = Network(self.config)
        self.wg = Wireguard(path)
        self.logger = logger
        self.path = path

    def getLatency(self,targets):
        ips = []
        for row in targets: ips.append(row['target'])
        latency =  self.fping(ips,5)
        if not latency:
            self.logger.warning("No pingable links found.")
            return False
        for ip,pings in latency.items():
            pings = pings[2:] #drop the first 2 pings
            pings.sort()
        for data in list(targets):
            for ip,pings in latency.items():
                if ip == data['target']:
                    if len(pings) < 5: self.logger.warning(f"Expected 5 pings, got {len(pings)} from {data['target']}, possible Packetloss")
                    current = int(self.getAvrg(pings) * 10)
                    if current > 65534: current = 65534
                    data['base'] = data['cost'] = current
                    if data['cost'] == 65534: self.logger.warning(f"Cannot reach {data['nic']} {data['target']}")
                    break
        if (len(targets) != len(latency)): self.logger.warning("Targets do not match expected responses.")
        return targets

    def getIPerf(self,targets):
        random.shuffle(targets)
        todo = []
        #we try to iperf a link 5 times
        for i in range(5):
            for row in targets:
                #skip already benchmarked links
                if 'cost' in row and row['cost'] != 20000: continue
                #benchmark
                self.logger.info(f"Running IPerf to {row['target']} on {row['nic']}")
                speed = int(self.iperf(row['target']))
                self.logger.info(f"{speed}Mbit's for {row['target']}")
                if speed == 0:
                    #if we fail to run the iperf, put on list
                    todo.append(row['target'])
                    row['cost'] = 20000
                    time.sleep(random.randint(2,10))
                else:
                    if row['target'] in todo: todo.remove(row['target'])
                    row['cost'] = 20000 - speed
            #when list is empty, exit
            if not todo: break
        return targets

    def genTargets(self,links):
        result,peers = [],[]
        for link in links:
            nic,ip,lastByte = link[0],link[2],link[3]
            origin = ip+lastByte
            #Client or Server roll the dice or rather not, so we ping the correct ip
            target = self.resolve(f"{ip}{int(lastByte)+1}",origin,31)
            subnet = f"{ip}0/30"
            targetIP = f"{ip}{int(lastByte)+1}" if target else f"{ip}{int(lastByte)-1}"
            if "peer" in nic: 
                peers.append({'nic':nic,'target':targetIP,'origin':origin,"subnet":subnet})
            else:
                result.append({'nic':nic,'target':targetIP,'origin':origin,"subnet":subnet})
        return result,peers

    def bird(self,override=False,skipIperf=False):
        #check if bird is running
        bird = self.cmd("systemctl status bird")[0]
        if not "running" in bird and override == False:
            self.logger.warning("bird not running")
            return False
        self.logger.info("Collecting Network data")
        configs = self.cmd('ip addr show')[0]
        links = re.findall(f"(({self.prefix})[A-Za-z0-9]+): <POINTOPOINT.*?inet ([0-9.]+\.)([0-9]+)",configs, re.MULTILINE | re.DOTALL)
        #filter out specific links
        links = [x for x in links if self.filter(x[0])]
        if not links: 
            self.logger.warning("No wireguard interfaces found") 
            return False
        self.logger.info("Getting Network targets")
        nodes,peers = self.genTargets(links)
        latencyModes = [0,1]
        if self.config['operationMode'] in latencyModes or skipIperf:
            self.logger.info("Latency messurement")
            latencyData = self.getLatency(nodes)
            if not latencyData: return False
            #if client adjust base latency to avoid transit
            for data in latencyData:
                linkID = re.findall(f"{self.config['prefix']}.*?([0-9]+)",data['nic'], re.MULTILINE)[0]
                if (int(linkID) >= 200 or int(self.config['id']) >= 200) and (data['cost'] + 1000) < 65534: data['cost'] += 1000
        elif self.config['operationMode'] == 2:
            self.logger.info("IPerf messurement")
            latencyData = self.getIPerf(nodes)
        self.logger.info("Generating config")
        bird = self.Templator.genBird(latencyData,peers,self.config)
        if bird == "": 
            self.logger.warning("No bird config generated")
            return False
        self.logger.info("Writing config")
        self.saveFile(bird,'/etc/bird/bird.conf')
        self.logger.info("Reloading bird")
        self.cmd("sudo systemctl reload bird")
        return latencyData,peers

    def mesh(self):
        #check if bird is running
        bird = self.cmd("systemctl status bird")[0]
        if not "running" in bird:
            self.logger.warning("bird not running")
            return False
        #wait for bird to fully bootstrap
        oldTargets,counter = [],0
        self.logger.info("Waiting for bird routes")
        for run in range(30):
            targets = self.Network.getRoutes()
            self.logger.debug(f"Run {run}/30, Counter {counter}, Got {targets} as targets")
            if oldTargets != targets:
                oldTargets = targets
                counter = 0
            else:
                counter += 1
                if counter == 8: break
            time.sleep(5)
        #when targets empty, abort
        if not targets: 
            self.logger.warning("bird returned no routes, did you setup bird?")
            return False
        #vxlan fuckn magic
        vxlan = self.cmd("bridge fdb show dev vxlan1 | grep dst")[0]
        for target in targets:
            ip = target.replace("0/30","1")
            splitted = ip.split(".")
            if not ip in vxlan: 
                self.cmd(f"sudo bridge fdb append 00:00:00:00:00:00 dev vxlan1 dst {ip}")
                self.cmd(f"sudo bridge fdb append 00:00:00:00:00:00 dev vxlan1v6 dst fd10:0:{splitted[2]}::1 permanent")