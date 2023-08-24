import random, time, json, re, os
from Class.wireguard import Wireguard
from Class.base import Base

class Diag(Base):

    def __init__(self,path,logger):
        self.logger = logger
        self.wg = Wireguard(path)
        self.path = path
        file = f"{path}/configs/"
        self.diagnostic = self.readConfig(f"{file}diagnostic.json")
        self.network = self.readConfig(f"{file}network.json")

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
            self.logger.info(f"Found dead link {link}")
            count, data, current = 0, links[link], int(time.time())
            parsed, remote = self.getRemote(data['local'])
            if not remote in self.diagnostic: self.diagnostic[remote] = {"cooldown":0}
            if current < self.diagnostic[remote]['cooldown']: continue
            self.diagnostic[remote]['cooldown'] = current + 3600
            for event,lost in list(self.network[remote]['packetloss'].items()):
                if int(event) > int(time.time()) and lost == 4: count += 1 
            if count < 20: continue
            endpoint = f"{parsed[1]}1"
            pings = self.fping([endpoint],3,True)
            if not pings[endpoint]:
                self.logger.info(f"Unable to reach endpoint {endpoint} for link {link}")
                continue
            self.logger.info(f"Dead link confirmed {link}")