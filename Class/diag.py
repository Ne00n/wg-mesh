import random, time, json, re, os
from Class.wireguard import Wireguard
from Class.base import Base

class Diag(Base):

    def __init__(self,path,logger):
        self.wg = Wireguard(path)
        self.logger = logger
        super().__init__()
        self.path = path
        self.diagnostic = self.readJson(f"{self.path}/configs/diagnostic.json")
        self.config = self.readJson(f'{self.path}/configs/config.json')

    def run(self):
        #refresh network.json on each run
        self.network = self.readJson(f"{self.path}/configs/network.json")
        self.logger.info("Starting diagnostic")
        if not os.path.isfile(f"{self.path}/configs/state.json"):
            self.logger.warning("state.json does not exist")
            return False
        targets = self.getRoutes()
        if not targets: 
            self.logger.warning("bird returned no routes, did you setup bird?")
            return False
        links = self.wg.getLinks()
        self.logger.info(f"Checking {len(links)} Links")
        offline,online = self.wg.checkLinks(links)
        self.logger.info(f"Found {len(offline)} dead link(s)")
        allowedLinkType = ["default","amneziawg"]
        for link in offline:
            count, data, current = 0, links[link], int(time.time())
            isDead = int(time.time()) - 21600 # 6 hours
            remote = data['remote']
            if "endpoint" in data['config'] and self.network[remote]['lastOnline'] < isDead:
                self.logger.warning(f"{link} overriding client check")
            elif "endpoint" in data['config']: 
                self.logger.debug(f"{link} is client, skipping")
                continue
            linkConfig = self.readJson(f'{self.path}/links/{data["filename"]}.json')
            #have to check the linkType, currently no logic for different link types so we just skip them for now
            if "linkType" in linkConfig and not linkConfig['linkType'] in allowedLinkType:
                self.logger.warning(f"{link} has non default linkType, skipping")
                continue
            if not remote in self.diagnostic: self.diagnostic[remote] = {"cooldown":0,"retries":0}
            if self.diagnostic[remote]['cooldown'] > current: 
                self.logger.debug(f"Skipping {link} due to cooldown")
                continue
            self.logger.info(f"Found dead link {link} ({remote})")
            self.diagnostic[remote]['cooldown'] = current + random.randint(21600,43200)
            self.diagnostic[remote]['retries'] += 1
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
            pings = self.fping([endpoint],3,True)
            if not pings[endpoint]:
                self.logger.info(f"Unable to reach vxlan endpoint {link} ({endpoint})")
                continue
            notifications = self.config['notifications']
            remotePublic = data['remotePublic']
            if remotePublic:
                self.logger.debug(f"Pinging public ip {remotePublic}")
                pings = self.fping([remotePublic],3,True)
                if not pings[remotePublic]:
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
                    self.logger.warning(f"MTR shows routing issue, skipping {link}")
                    continue
            self.logger.info(f"Dead link confirmed {link} ({remote})")
            self.logger.info(f"Disconnecting {link}")
            status = self.wg.disconnect([link])
            if not status[link]['success']:
                self.logger.warning(f"Failed to disconnect {link} ({remote})")
                if status[link]['message'] == "invalid link":
                    self.wg.removeInterface(link.replace(".sh",""))
                    self.logger.info(f"Removed link {link} ({remote})")
                else:
                    if notifications['enabled'] and notifications['gotifyDiag']: 
                        self.wg.notify(notifications['gotifyDiag'],f"{link} disconnect failure ({self.diagnostic[remote]['retries']})",f"Node {self.config['id']} failed to disconnect {link}")
                    continue
            time.sleep(3)
            if "linkType" in linkConfig:
                self.logger.info(f"Current linkType is {linkConfig['linkType']}")
            self.logger.debug(f"Selecting linkType")
            linkData = self.wg.AskProtocol(f"http://{endpoint}:8080")
            linkType = ""
            if linkData:
                availableLinkTypes = self.wg.availableLinkTypes(self.config,linkData)
                linkType = random.choice(availableLinkTypes)
                self.logger.info(f"Selected linkType is {linkType}")
            self.logger.info(f"Reconnecting {link}")
            port = random.randint(1024, 50000)
            status = self.wg.connect(f"http://{endpoint}:8080","dummy",linkType,port)
            if status['v4'] or status['v6']:
                self.logger.info(f"Reconnected {link} ({remote}) with Port {port}")
                if notifications['enabled'] and notifications['gotifyDiag']: 
                    self.wg.notify(notifications['gotifyDiag'],f"{link} reconnected ({self.diagnostic[remote]['retries']})",f"Node {self.config['id']} reconnected {link}")
            else:
                self.logger.info(f"Could not reconnect {link} ({remote})")
                if notifications['enabled'] and notifications['gotifyDiag']: 
                    self.wg.notify(notifications['gotifyDiag'],f"{link} reconnect failure",f"Node {self.config['id']} failed to reconnect {link}")
        self.logger.info(f"Loop done")
        self.saveJson(self.diagnostic,f"{self.path}/configs/diagnostic.json")
        return True