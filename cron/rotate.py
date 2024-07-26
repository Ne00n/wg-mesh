#!/usr/bin/python3
import logging, secrets, time, sys, os
sys.path.append("..") # Adds higher directory to python modules path.
from logging.handlers import RotatingFileHandler
from Class.wireguard import Wireguard

path = os.path.dirname(os.path.realpath(__file__))
path = path.replace("/cron","")

#logging
level = "info"
levels = {'critical': logging.CRITICAL,'error': logging.ERROR,'warning': logging.WARNING,'info': logging.INFO,'debug': logging.DEBUG}
stream_handler = logging.StreamHandler()
stream_handler.setLevel(levels[level])
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',datefmt='%d.%m.%Y %H:%M:%S',level=levels[level],handlers=[RotatingFileHandler(maxBytes=10000000,backupCount=5,filename=f"{path}/logs/rotate.log"),stream_handler])
logger = logging.getLogger()

wg = Wireguard(path)
config = wg.getConfig()
path,links = f'{path}/links/',[]

targetInterface = ""
if len(sys.argv) == 2: targetInterface = sys.argv[1]

waitUntil = 0
while True:
    currentTime = int(time.time())
    if currentTime > waitUntil:
        links = wg.getLinks()
        for link, data in links.items():
            link = wg.filterInterface(link)
            if targetInterface and link != targetInterface: continue
            if "XOR" in data['config'] and "endpoint" in data['config']:
                logger.info(f"{link} swapping xor keys")
                interfaceRemote = wg.getInterfaceRemote(link)
                logger.info(f"{link} increasing remote cost")
                req = wg.call(f'http://{data["vxlan"]}:{config["listenPort"]}/update',{"cost":5000,"publicKeyServer":data['publicKey'],"interface":interfaceRemote},'PATCH')
                if not req:
                    logger.info(f"{link} Failed to increase remote cost")
                    continue
                logger.info(f"{link} increasing local cost")
                result = wg.setCost(link,5000)
                if not result:
                    logger.info(f"Failed to increase cost")
                    continue
                logger.info(f"{link} waiting 300s for cost to apply")
                time.sleep(500)
                logger.info(f"{link} shutting link down")
                wg.setInterface(link,"down")
                logger.info(f"{link} updating remote xor keys")
                xorKey = secrets.token_urlsafe(24)
                req = wg.call(f'http://{data["vxlan"]}:{config["listenPort"]}/update',{"xorKey":xorKey,"publicKeyServer":data['publicKey'],"interface":interfaceRemote},'PATCH')
                if not req:
                    logger.info(f"{link} Failed to update remote xor keys")
                    logger.info(f"{link} restoring link state")
                    wg.setCost(link,0)
                    wg.setInterface(link,"up")
                    continue
                logger.info(f"{link} updating local xor keys")
                wg.updateLink(link,{'xorKey':xorKey})
                logger.info(f"{link} starting link")
                wg.setInterface(link,"up")
                logger.info(f"{link} removing remote cost")
                req = wg.call(f'http://{data["vxlan"]}:{config["listenPort"]}/update',{"cost":0,"publicKeyServer":data['publicKey'],"interface":interfaceRemote},'PATCH')
                if not req: logger.info(f"{link} Failed to remove remote cost")
                logger.info(f"{link} removing local cost")
                wg.setCost(link,0)
                logger.info(f"{link} done swapping xor keys")
        #run this twice per day
        waitUntil = currentTime + (3600 * 12)
    else:
        time.sleep(30)