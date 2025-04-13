import random, time, json, re, os
from Class.wireguard import Wireguard
from Class.base import Base

class Rotate(Base):

    def __init__(self,path,logger):
        self.logger = logger
        self.wg = Wireguard(path)
        self.path = path
        self.config = self.readJson(f'{self.path}/configs/config.json')
        self.subnetPrefixSplitted = self.config['subnet'].split(".")

    def run(self,targetInterface):
        self.rotate = self.readJson(f"{self.path}/configs/rotate.json")
        self.logger.info(f"Running")
        links = self.wg.getLinks()
        for link, data in links.items():
            link = self.wg.filterInterface(link)
            if targetInterface and link != targetInterface: continue
            if "XOR" in data['config'] and "endpoint" in data['config']:
                if not link in self.rotate: self.rotate[link] = {"cooldown":0}
                if self.rotate[link]['cooldown'] > int(time.time()): 
                    self.logger.info(f"Skipping {link} due to cooldown")
                    continue
                #rotate every 5 to 7 hours
                self.rotate[link]['cooldown'] = int(time.time()) + random.randint(18000,25200)
                self.logger.info(f"{link} swapping xor keys")
                interfaceRemote = self.wg.getInterfaceRemote(link)
                self.logger.info(f"{link} increasing remote cost")
                req = setRemoteCost(5000)
                if not req:
                    self.logger.warning(f"{link} Failed to increase remote cost")
                    if notifications['enabled']: self.wg.notify(config['notifications']['gotifyError'],f"{link} xor exchange error",f"Node {config['id']} Failed to increase remote cost")
                    continue
                self.logger.info(f"{link} increasing local cost")
                result = self.wg.setCost(link,5000)
                if not result:
                    self.logger.warning(f"Failed to increase local cost")
                    if notifications['enabled']: self.wg.notify(config['notifications']['gotifyError'],f"{link} xor exchange error",f"Node {config['id']} Failed to increase local cost")
                    req = setRemoteCost(0)
                    if not req: self.logger.warning(f"{link} Failed to remove remote cost")
                    continue
                self.logger.info(f"{link} waiting 60s for cost to apply")
                time.sleep(60)
                self.logger.info(f"{link} shutting link down")
                self.wg.setInterface(link,"down")
                self.logger.info(f"{link} updating remote xor keys")
                xorKey = secrets.token_urlsafe(24)
                req = self.wg.call(f'http://{data["vxlan"]}:{config["listenPort"]}/update',{"xorKey":xorKey,"publicKeyServer":data['publicKey'],"interface":interfaceRemote},'PATCH')
                if not req:
                    self.logger.warning(f"{link} Failed to update remote xor keys")
                    if notifications['enabled']: self.wg.notify(config['notifications']['gotifyError'],f"{link} xor exchange error",f"Node {config['id']} Failed to update remote xor keys")
                    self.logger.info(f"{link} restoring link state")
                    self.wg.setCost(link,0)
                    self.wg.setInterface(link,"up")
                    setRemoteCost(0)
                    self.logger.info(f"{link} restored link state")
                    continue
                self.logger.info(f"{link} updating local xor keys")
                self.wg.updateLink(link,{'xorKey':xorKey})
                self.logger.info(f"{link} starting link")
                self.wg.setInterface(link,"up")
                self.logger.info(f"{link} removing remote cost")
                req = setRemoteCost(0)
                if not req: 
                    self.logger.warning(f"{link} Failed to remove remote cost")
                    if notifications['enabled']: self.wg.notify(config['notifications']['gotifyError'],f"{link} xor exchange error",f"Node {config['id']} Failed to remove remote cost")
                self.logger.info(f"{link} removing local cost")
                result = self.wg.setCost(link,0)
                if not result: 
                    self.logger.warning(f"{link} Failed to remove local cost")
                    if notifications['enabled']: self.wg.notify(config['notifications']['gotifyError'],f"{link} xor exchange error",f"Node {config['id']} Failed to remove local cost")
                self.logger.info(f"{link} Testing connectivity")
                time.sleep(2)
                latency =  self.wg.fping([data['remote']],5,True)
                if not latency:
                    self.logger.warning(f"{link} Unable to verify connectivity")
                    if notifications['enabled']: self.wg.notify(config['notifications']['gotifyError'],f"{link} xor exchange error",f"Node {config['id']} Unable to verify connectivity")
                self.logger.info(f"{link} done swapping xor keys")
        #run every hour
        self.wg.saveJson(self.rotate,f"{self.path}/configs/rotate.json")