import random, time, json, re, os
from Class.wireguard import Wireguard
from Class.base import Base

class Diag(Base):

    def __init__(self,path,logger):
        self.logger = logger
        self.wg = Wireguard(path)
        self.path = path
        self.diagnostic = self.readJson(f"{self.path}/configs/diagnostic.json")
        self.network = self.readJson(f"{self.path}/configs/network.json")
        self.config = self.readJson(f'{self.path}/configs/config.json')
        self.subnetPrefixSplitted = self.config['subnet'].split(".")

    def run(self):
        self.logger.info("Starting diagnostic")
        if not os.path.isfile(f"{self.path}/configs/state.json"):
            self.logger.warning("state.json does not exist")
            return False
        targets = self.getRoutes()
        if not targets: 
            self.logger.warning("bird returned no routes, did you setup bird?")
            return False
        links = self.wg.getLinks()
        self.logger.info("Checking Links")
        offline,online = self.wg.checkLinks(links)
        for link in offline:
            count, data, current = 0, links[link], int(time.time())
            if not "endpoint" in data['config']: continue
            linkConfig = self.readJson(f'{self.path}/links/{data["filename"]}.json')
            #have to check the linkType, currently no logic for different link types so we just skip them for now
            if "linkType" in linkConfig and linkConfig['linkType'] != "default":
                self.logger.warning(f"{link} has non default linkType, skipping")
                continue
            parsed, remote = self.getRemote(data['config'],self.subnetPrefixSplitted)
            self.logger.info(f"Found dead link {link} ({remote})")
            if not remote in self.diagnostic: self.diagnostic[remote] = {"cooldown":0}
            if self.diagnostic[remote]['cooldown'] > current: 
                self.logger.info(f"Skipping {link} due to cooldown")
                continue
            self.diagnostic[remote]['cooldown'] = current + random.randint(43200,57600)
            if not remote in self.network:
                self.logger.warning(f"{link} no data in network.json, skipping")
                continue
            for event,row in list(self.network[remote]['packetloss'].items()):
                if int(event) > int(time.time()) and row['peak'] == 4: count += 1
            if count < 20: 
                self.logger.info(f"{link} got {count}, 20 are needed for confirmation")
                continue
            endpoint = f"{parsed[1]}1"
            pings = self.fping([endpoint],3,True)
            if not pings[endpoint]:
                self.logger.info(f"Unable to reach endpoint {link} ({endpoint})")
                continue
            self.logger.info(f"Dead link confirmed {link} ({remote})")
            self.logger.info(f"Disconnecting {link}")
            status = self.wg.disconnect([link])
            if not status[link]:
                self.logger.warning(f"Failed to disconnect {link} ({remote})")
                continue
            time.sleep(3)
            self.logger.info(f"Reconnecting {link}")
            port = random.randint(1024, 50000)
            status = self.wg.connect(f"http://{endpoint}:8080","dummy","",port)
            if status['v4'] or status['v6']:
                self.logger.info(f"Reconnected {link} ({remote}) with Port {port}")
            else:
                self.logger.info(f"Could not reconnect {link} ({remote})")
        self.logger.info(f"Loop done")
        self.saveJson(self.diagnostic,f"{self.path}/configs/diagnostic.json")
        return True