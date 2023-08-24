import random, time, json, re, os
from Class.wireguard import Wireguard
from Class.base import Base

class Diag(Base):

    def __init__(self,path,logger):
        self.logger = logger
        self.wg = Wireguard(path)
        self.path = path
        self.diagnostic = self.readConfig(f"{self.path}/configs/diagnostic.json")
        self.network = self.readConfig(f"{self.path}/configs/network.json")

    def run(self):
        self.logger.info("Starting diagnostic")
        if not os.path.isfile(f"{self.path}/configs/state.json"):
            self.logger.warning("state.json does not exist")
            exit()
        targets = self.getRoutes()
        if not targets: 
            self.logger.warning("bird returned no routes, did you setup bird?")
            exit()
        links = self.wg.getLinks()
        self.logger.info("Checking Links")
        offline,online = self.wg.checkLinks(links)
        for link in offline:
            if "Serv" in link: continue
            count, data, current = 0, links[link], int(time.time())
            parsed, remote = self.getRemote(data['local'])
            self.logger.info(f"Found dead link {link} ({remote})")
            if not remote in self.diagnostic: self.diagnostic[remote] = {"cooldown":0}
            if current < self.diagnostic[remote]['cooldown']: continue
            self.diagnostic[remote]['cooldown'] = current + 3600
            for event,lost in list(self.network[remote]['packetloss'].items()):
                if int(event) > int(time.time()) and lost == 4: count += 1 
            if count < 20: continue
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
            self.logger.info(f"Reconnecting {link}")
            port = random.randint(1024, 50000)
            status = self.wg.connect(f"http://{endpoint}:8080","dummy","",port)
            if status:
                self.logger.info(f"Reconnected {link} ({remote}) with Port {port}")
            else:
                self.logger.info(f"Could not reconnect {link} ({remote})")
        self.saveJson(f"{self.path}/configs/diagnostic.json")