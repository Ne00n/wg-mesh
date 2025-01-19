import random, time, json, re, os
from Class.templator import Templator
from Class.wireguard import Wireguard
from Class.base import Base

class Bird(Base):
    Templator = Templator()

    def __init__(self,path,logger):
        self.config = self.readJson(f'{path}/configs/config.json')
        self.subnetPrefixSplitted = self.config['subnet'].split(".")
        self.prefix = self.config['prefix']
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
        for entry,row in latency.items():
            row = row[2:] #drop the first 2 pings
            row.sort()
        for data in list(targets):
            for entry,row in latency.items():
                if entry == data['target']:
                    if len(row) < 5: self.logger.warning(f"Expected 5 pings, got {len(row)} from {data['target']}, possible Packetloss")
                    data['cost'] = self.getAvrg(row,False)
                    if data['cost'] == 65535: self.logger.warning(f"Cannot reach {data['nic']} {data['target']}")
                #apparently fping 4.2 and 5.0 result in different outputs, neat, so we keep this
                elif data['target'] not in latency and not "latency" in data:
                    self.logger.warning(f"Cannot reach {data['nic']} {data['target']}")
                    data['cost'] = 65535
        if (len(targets) != len(latency)): self.logger.warning("Targets do not match expected responses.")
        return targets

    def getIPerf(self,targets):
        random.shuffle(targets)
        todo = []
        #we try to iperf a link 5 times
        for i in range(5):
            for row in targets:
                #skip already benchmarked links
                if 'cost' in row: continue
                #benchmark
                self.logger.info(f"Running IPerf to {row['target']}")
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
            if target == True:
                targetIP = f"{ip}{int(lastByte)+1}"
            else:
                targetIP = f"{ip}{int(lastByte)-1}"
            if "Peer" in nic: peers.append({'nic':nic,'target':targetIP,'origin':origin})
            result.append({'nic':nic,'target':targetIP,'origin':origin})
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
                if (int(linkID) >= 200 or int(self.config['id']) >= 200) and (data['cost'] + 10000) < 65535: data['cost'] += 10000
        elif self.config['operationMode'] == 2:
            self.logger.info("IPerf messurement")
            latencyData = self.getIPerf(nodes)
        latencyDataNoGroup = latencyData
        latencyData = self.wg.groupByArea(latencyData)
        self.logger.info("Generating config")
        bird = self.Templator.genBird(latencyData,peers,self.config)
        if bird == "": 
            self.logger.warning("No bird config generated")
            return False
        self.logger.info("Writing config")
        self.saveFile(bird,'/etc/bird/bird.conf')
        self.logger.info("Reloading bird")
        self.cmd("sudo systemctl reload bird")
        return latencyDataNoGroup,peers

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
            targets = self.getRoutes(self.subnetPrefixSplitted)
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
                self.cmd(f"sudo bridge fdb append 00:00:00:00:00:00 dev vxlan1v6 dst fd10:0:{splitted[2]}::1")
        #To prevent creating connections to new nodes joined afterwards, save state
        if os.path.isfile(f"{self.path}/configs/state.json"):
            self.logger.debug("state.json already exist, skipping")
        else:
            #fetch network interfaces and parse
            configs = self.cmd('ip addr show')[0]
            links = self.getBirdLinks(configs,self.prefix,self.subnetPrefixSplitted)
            localIP = f"{'.'.join(self.config['subnet'].split('.')[:2])}.{self.config['id']}.1"
            if not links: 
                self.logger.warning("No wireguard interfaces found") 
                return False
            #remove local machine from list
            for ip in list(targets):
                if self.resolve(localIP,ip.replace("/30",""),30):
                    targets.remove(ip)
            #run against existing links
            for ip in list(targets):
                for link in links:
                    if self.resolve(link[1],ip.replace("/30",""),24):
                        #multiple links in the same subnet
                        if ip in targets: targets.remove(ip)
            #run against local link names
            for ip in list(targets):
                for link in links:
                    splitted = ip.split(".")
                    if f"pipe{splitted[2]}" in link[0]:
                        #multiple links in the same subnet
                        if ip in targets: targets.remove(ip)
            self.logger.info(f"Possible targets {targets}")
            #wireguard
            self.logger.info("meshing")
            results = {}
            for target in targets:
                targetSplit = target.split(".")
                #reserve 10.0.200+ for clients, don't mesh
                if int(targetSplit[2]) >= 200: continue
                dest = target.replace(".0/30",".1")
                #no token needed but external IP for the client
                self.logger.info(f"Setting up link to {dest}")
                status = self.wg.connect(f"http://{dest}:{self.config['listenPort']}")
                if status['v4'] or status['v6']:
                    results[target] = True
                    self.logger.info(f"Link established to http://{dest}:{self.config['listenPort']}")
                else:
                    results[target] = False
                    self.logger.warning(f"Failed to setup link to http://{dest}:{self.config['listenPort']}")
            self.logger.info("saving state.json")
            with open(f"{self.path}/configs/state.json", 'w') as f: json.dump(results, f ,indent=4)