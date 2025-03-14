#!/usr/bin/python3
import logging, secrets, signal, random, time, sys, os
sys.path.append("..") # Adds higher directory to python modules path.
from logging.handlers import RotatingFileHandler
from Class.wireguard import Wireguard
import systemd.daemon

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
rotate = wg.readJson(f"{path}/configs/rotate.json")
notifications = config['notifications']

targetInterface = ""
if len(sys.argv) == 2: targetInterface = sys.argv[1]

def setRemoteCost(cost=0):
    return wg.call(f'http://{data["vxlan"]}:{config["listenPort"]}/update',{"cost":cost,"publicKeyServer":data['publicKey'],"interface":interfaceRemote},'PATCH')

shutdown = False
def gracefulExit(signal_number,stack_frame):
    systemd.daemon.notify('STOPPING=1')
    logger.info(f"Stopping")
    global shutdown
    shutdown = True

signal.signal(signal.SIGINT, gracefulExit)
signal.signal(signal.SIGTERM, gracefulExit)
systemd.daemon.notify('READY=1')
logger.info(f"Ready")

waitUntil = 0
while not shutdown:
    currentTime = int(time.time())
    if currentTime > waitUntil:
        #we need a lock file, since rotate and diag could conflict with each other
        if os.path.isfile(f"{path}/cron/lock"): 
            time.sleep(60)
            continue
        open(f"{path}/cron/lock",'w').close()
        links = wg.getLinks()
        for link, data in links.items():
            link = wg.filterInterface(link)
            if targetInterface and link != targetInterface: continue
            if "XOR" in data['config'] and "endpoint" in data['config']:
                if not link in rotate: rotate[link] = {"cooldown":0}
                if rotate[link]['cooldown'] > int(time.time()): 
                    logger.info(f"Skipping {link} due to cooldown")
                    continue
                #rotate every 5 to 7 hours
                rotate[link]['cooldown'] = int(time.time()) + random.randint(18000,25200)
                logger.info(f"{link} swapping xor keys")
                interfaceRemote = wg.getInterfaceRemote(link)
                logger.info(f"{link} increasing remote cost")
                req = setRemoteCost(5000)
                if not req:
                    logger.warning(f"{link} Failed to increase remote cost")
                    if notifications['enabled']: wg.notify(config['notifications']['gotifyError'],f"{link} xor exchange error",f"Node {config['id']} Failed to increase remote cost")
                    continue
                logger.info(f"{link} increasing local cost")
                result = wg.setCost(link,5000)
                if not result:
                    logger.warning(f"Failed to increase local cost")
                    if notifications['enabled']: wg.notify(config['notifications']['gotifyError'],f"{link} xor exchange error",f"Node {config['id']} Failed to increase local cost")
                    req = setRemoteCost(0)
                    if not req: logger.warning(f"{link} Failed to remove remote cost")
                    continue
                logger.info(f"{link} waiting 60s for cost to apply")
                time.sleep(60)
                logger.info(f"{link} shutting link down")
                wg.setInterface(link,"down")
                logger.info(f"{link} updating remote xor keys")
                xorKey = secrets.token_urlsafe(24)
                req = wg.call(f'http://{data["vxlan"]}:{config["listenPort"]}/update',{"xorKey":xorKey,"publicKeyServer":data['publicKey'],"interface":interfaceRemote},'PATCH')
                if not req:
                    logger.warning(f"{link} Failed to update remote xor keys")
                    if notifications['enabled']: wg.notify(config['notifications']['gotifyError'],f"{link} xor exchange error",f"Node {config['id']} Failed to update remote xor keys")
                    logger.info(f"{link} restoring link state")
                    wg.setCost(link,0)
                    wg.setInterface(link,"up")
                    setRemoteCost(0)
                    logger.info(f"{link} restored link state")
                    continue
                logger.info(f"{link} updating local xor keys")
                wg.updateLink(link,{'xorKey':xorKey})
                logger.info(f"{link} starting link")
                wg.setInterface(link,"up")
                logger.info(f"{link} removing remote cost")
                req = setRemoteCost(0)
                if not req: 
                    logger.warning(f"{link} Failed to remove remote cost")
                    if notifications['enabled']: wg.notify(config['notifications']['gotifyError'],f"{link} xor exchange error",f"Node {config['id']} Failed to remove remote cost")
                logger.info(f"{link} removing local cost")
                result = wg.setCost(link,0)
                if not result: 
                    logger.warning(f"{link} Failed to remove local cost")
                    if notifications['enabled']: wg.notify(config['notifications']['gotifyError'],f"{link} xor exchange error",f"Node {config['id']} Failed to remove local cost")
                logger.info(f"{link} Testing connectivity")
                time.sleep(2)
                latency =  wg.fping([data['remote']],5,True)
                if not latency:
                    logger.warning(f"{link} Unable to verify connectivity")
                    if notifications['enabled']: wg.notify(config['notifications']['gotifyError'],f"{link} xor exchange error",f"Node {config['id']} Unable to verify connectivity")
                logger.info(f"{link} done swapping xor keys")
        #run every hour
        waitUntil = currentTime + 3600
        wg.saveJson(rotate,f"{path}/configs/rotate.json")
        os.unlink(f"{path}/cron/lock")
    else:
        time.sleep(10)