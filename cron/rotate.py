#!/usr/bin/python3
import logging, secrets, signal, random, time, sys, os
sys.path.append("..") # Adds higher directory to python modules path.
from logging.handlers import RotatingFileHandler
from Class.wireguard import Wireguard
from Class.rotate import Rotate
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
notifications = config['notifications']

targetInterface = ""
if len(sys.argv) == 2: targetInterface = sys.argv[1]

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

rotate = Rotate(path,logger)
waitUntil = 0
while not shutdown:
    currentTime = int(time.time())
    if currentTime > waitUntil:
        #we need a lock file, since rotate and diag could conflict with each other
        if os.path.isfile(f"{path}/cron/lock"):
            logger.info(f"Waiting for lock") 
            time.sleep(60)
            continue
        open(f"{path}/cron/lock",'w').close()
        rotate.run(targetInterface)
        os.unlink(f"{path}/cron/lock")
        waitUntil = currentTime + 3600
    else:
        time.sleep(10)