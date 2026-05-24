import random, time, json, re, os
from Class.wireguard import Wireguard
from Class.network import Network
from Class.base import Base

class Diag(Base):

    def __init__(self,path,logger):
        self.wg = Wireguard(path)
        self.logger = logger
        super().__init__()
        self.path = path
        self.diagnostic = self.readFile(f"{self.path}/configs/diagnostic.json")
        self.config = self.readFile(f'{self.path}/configs/config.json')
        self.Network = Network(self.config)

    def randDelay(self,start=21600,end=43200):
        return int(time.time()) + random.randint(start,end)

    def updateDiagnostic(self,id,cooldown=0):
        if cooldown: cooldown = self.randDelay(3600,7200)
        pings = {'direct4':[],'direct6':[],'indirect':[]}
        stats = {'retries':0,'routing':0,'runMesh':0}
        if not id in self.diagnostic: self.diagnostic[id] = {"cooldown":cooldown,"stats":stats,"events":{},"pings":pings}
        if not "events" in self.diagnostic[id]: self.diagnostic[id]['events'] = {}
        if not "stats" in self.diagnostic[id]: self.diagnostic[id]['stats'] = stats
        if not "pings" in self.diagnostic[id]: self.diagnostic[id]['pings'] = pings
        if "retries" in self.diagnostic[id]: del self.diagnostic[id]['retries']

    def runDiagnostic(self):
        #refresh network.json on each run
        self.network = self.readFile(f"{self.path}/configs/network.json")
        self.logger.info("Starting diagnostic")
        targets = self.wg.Network.getRoutes()
        if not targets: 
            self.logger.warning("bird returned no routes, did you setup bird?")
            return False
        links = self.wg.getLinks()
        self.logger.info(f"Checking {len(links)} Links")
        offline,online = self.wg.checkLinks(links)
        self.logger.info(f"Found {len(offline)} dead link(s)")
        for link in offline:
            count, data, current = 0, links[link], int(time.time())
            isDead = int(time.time()) - 50400 # 14 hours
            remote = data['remote']
            if "endpoint" in data['config'] and 'lastOnline' in self.network[remote] and self.network[remote]['lastOnline'] < isDead:
                self.logger.warning(f"{link} overriding client check")
            elif "endpoint" in data['config']: 
                self.logger.debug(f"{link} is client, skipping")
                continue
            self.updateDiagnostic(remote)
            if self.diagnostic[remote]['cooldown'] > current: 
                self.logger.debug(f"Skipping {link} due to cooldown")
                continue
            self.logger.info(f"Found dead link {link} ({remote})")
            self.diagnostic[remote]['cooldown'] = self.randDelay()
            self.diagnostic[remote]['stats']['retries'] += 1
            if not remote in self.network:
                self.logger.warning(f"{link} no data in network.json, skipping")
                continue
            for event,row in list(self.network[remote]['packetloss'].items()):
                if int(event) > int(time.time()) and row['peak'] == 4: count += 1
            if count < 20: 
                self.logger.info(f"{link} got {count}, 20 are needed for confirmation")
                continue
            endpoint = data['vxlan']
            self.logger.debug(f"Pinging vxlan {endpoint}")
            pings = self.fping([endpoint],3)
            if not pings[endpoint]:
                self.logger.info(f"Unable to reach vxlan endpoint {link} ({endpoint})")
                continue
            notifications = self.config['notifications']
            remotePublic = data['remotePublic']
            if remotePublic:
                self.logger.debug(f"Pinging public ip {remotePublic}")
                pings = self.fping([remotePublic],3)
                if not pings[remotePublic]:
                    self.diagnostic[remote]['stats']['routing'] += 1
                    self.logger.info(f"Unable to reach public ip address, likely routing problems {link}")
                    continue
                if len(pings[remotePublic]) != 3:
                    self.logger.info(f"Link {link} has packet loss, skipping for now")
                    continue
                self.logger.debug(f"Running MTR")
                mtr = self.cmd(f'mtr {remotePublic} --report --report-cycles 3 --no-dns')
                #if the mtr fails to run, grab the error message instead
                if not mtr[0] and mtr[1]: mtr[0] = mtr[1]
                mtrLines = mtr[0].splitlines()
                mtrLastLine = mtrLines[len(mtrLines) -1]
                if "???" in mtrLastLine:
                    self.diagnostic[remote]['stats']['routing'] += 1
                    self.logger.warning(f"MTR shows routing issue, skipping {link}")
                    continue
            self.logger.info(f"Dead link confirmed {link} ({remote})")
            self.logger.info(f"Disconnecting {link}")
            status = self.wg.disconnect([link])
            if not status[link]['status']:
                self.logger.warning(f"Failed to disconnect {link} ({remote})")
                allowedCodes = ["invalid public key","invalid link"]
                if status[link]['message'] in allowedCodes:
                    self.wg.removeInterface(link.replace(".sh",""))
                    self.logger.info(f"Removed link {link} ({remote})")
                else:
                    if notifications['enabled'] and notifications['gotifyDiag']: 
                        self.wg.notify(notifications['gotifyDiag'],f"{link} disconnect failure ({self.diagnostic[remote]['stats']['retries']})",f"Node {self.config['id']} failed to disconnect {link}")
                    continue
            time.sleep(3)
            linkConfig = self.readFile(f'{self.path}/links/{data["filename"]}.json')
            if "linkType" in linkConfig:
                self.logger.info(f"Current linkType is {linkConfig['linkType']}")
            self.logger.debug(f"Selecting linkType")
            linkData = self.wg.AskProtocol(f"http://{endpoint}:8080")
            linkType = ""
            if linkData:
                availableLinkTypes = self.wg.availableLinkTypes(self.config,linkData)
                linkType = random.choice(availableLinkTypes)
                self.logger.info(f"Selected linkType is {linkType}")
            self.logger.info(f"Checking latency")
            connect = self.shouldConnect(endpoint)
            if not connect['connect']:
                self.logger.info(f"Skipping {endpoint}, direct latency to high, {connect['direct4']}/{connect['direct6']}ms vs {connect['indirect']}ms")
                continue
            self.logger.info(f"Reconnecting {link}")
            port = random.randint(1024, 65000)
            status = self.wg.connect(f"http://{endpoint}:8080","dummy",linkType,port)
            if status['ipv4']['status'] or status['ipv6']['status']:
                self.logger.info(f"Reconnected {link} ({remote}) with Port {port}")
                if notifications['enabled'] and notifications['gotifyDiag']: 
                    self.wg.notify(notifications['gotifyDiag'],f"{link} reconnected ({self.diagnostic[remote]['stats']['retries']})",f"Node {self.config['id']} reconnected {link}")
                    self.diagnostic[remote]['events'][int(time.time())] = {"linkType":linkType,"port":port}
            else:
                self.logger.info(f"Could not reconnect {link} ({remote})")
                if notifications['enabled'] and notifications['gotifyDiag']: 
                    self.wg.notify(notifications['gotifyDiag'],f"{link} reconnect failure",f"Node {self.config['id']} failed to reconnect {link}")
        self.saveFile(self.diagnostic,f"{self.path}/configs/diagnostic.json")
        self.logger.info(f"Diagnostics done")

    def run(self):
        if not os.path.isfile(f"{self.path}/configs/state.json"):
            self.logger.warning("state.json does not exist")
            return False
        self.runDiagnostic()
        if self.config['linkSettings']['reMesh']: 
            self.runMesh()
            self.logger.info("Done re-meshing")
            self.saveFile(self.diagnostic,f"{self.path}/configs/diagnostic.json")
        self.logger.info(f"Loop done")
        return True

    def runMesh(self):
        self.logger.info(f"Starting re-meshing")
        if int(self.config['id']) >= 200:
            self.logger.info("Skipping re-mesh, ID is in client range")
        targets = self.Network.getRoutes()
        if not targets: 
            self.logger.warning("Skipping re-mesh, no routes from bird")
            return False
        links = self.Network.getBirdLinks()
        if not links: 
            self.logger.warning("Skipping re-mesh, no links found") 
            return False
        localIP = f"{'.'.join(self.config['subnet'].split('.')[:2])}.{self.config['id']}.1"
        targets = self.Network.filterLocalIP(targets,localIP)
        targets = self.Network.filterExisting(targets,links)
        targets = self.Network.filterLocalLinks(targets,links)
        targets = self.Network.filterIDs(targets,True)
        if not targets: return True
        random.shuffle(targets)
        self.logger.info(f"Possible targets {targets}")
        for target in targets:
            dest = target.replace(".0/30",".1")
            self.updateDiagnostic(dest,1)
            if self.diagnostic[dest]['cooldown'] > int(time.time()): 
                self.logger.debug(f"Skipping {dest}, due to cooldown")
                continue
            self.diagnostic[dest]['cooldown'] = self.randDelay()
            self.diagnostic[dest]['stats']['runMesh'] += 1
            self.logger.info(f"Checking latency for {dest}")
            connect = self.shouldConnect(dest)
            if not connect['connect']:
                self.logger.info(f"Skipping {dest}, direct latency to high, {connect['direct4']}/{connect['direct6']}ms vs {connect['indirect']}ms")
                continue
            self.logger.info(f"Setting up link to {dest}")
            status = self.wg.connect(dest=f"http://{dest}:{self.config['listenPort']}",protocols=connect['connect'])
            if status['ipv4']['status'] or status['ipv6']['status']:
                self.logger.info(f"Link established to http://{dest}:{self.config['listenPort']}")
                break
            else:
                self.logger.warning(f"Failed to setup link to http://{dest}:{self.config['listenPort']}")
        return True

    def shouldConnect(self,dest):
        data = self.wg.AskProtocol(f"http://{dest}:{self.config['listenPort']}")
        response = {"indirect":-1,"direct4":9999,"direct6":9999,"connect":[]}
        if not data:
            self.logger.info(f"Unable to fetch connectivity info from {dest}")
            return response
        mapping, toPing = {"dest":dest,"ipv4":"","ipv6":""}, [dest]
        if data['connectivity']['ipv4'] and self.config['connectivity']['ipv4']: 
            toPing.append(data['connectivity']['ipv4'])
            mapping['ipv4'] = data['connectivity']['ipv4']
        if data['connectivity']['ipv6'] and self.config['connectivity']['ipv6']: 
            toPing.append(data['connectivity']['ipv6'])
            mapping['ipv6'] = data['connectivity']['ipv6']
        pings = self.fping(toPing,10)
        for ip, results in pings.items():
            current = int(self.getAvrg(results))
            if ip == mapping['dest']: 
                response['indirect'] = current
                self.diagnostic[dest]['pings']['indirect'].append(current)
                self.diagnostic[dest]['pings']['indirect'][-6:]
            if ip == mapping['ipv4']: 
                response['direct4'] = current
                self.diagnostic[dest]['pings']['direct4'].append(current)
                self.diagnostic[dest]['pings']['direct4'][-6:]
            if ip == mapping['ipv6']: 
                response['direct6'] = current
                self.diagnostic[dest]['pings']['direct6'].append(current)
                self.diagnostic[dest]['pings']['direct6'][-6:]

        diag = self.diagnostic[dest]['pings']
        if self.getAvrg(diag['direct4']) < self.getAvrg(diag['indirect']) and len(diag['direct4']) > 2: 
            response['connect'].append("ipv4")
        if self.getAvrg(diag['direct6']) < self.getAvrg(diag['indirect']) and len(diag['direct6']) > 2: 
            response['connect'].append("ipv6")
        return response