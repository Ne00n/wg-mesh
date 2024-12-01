#!/usr/bin/python3
import logging, threading, shutil, queue, time, sys, os
sys.path.append("..") # Adds higher directory to python modules path.
from logging.handlers import RotatingFileHandler
from Class.latency import Latency
from Class.bird import Bird

path = os.path.dirname(os.path.realpath(__file__))
path = path.replace("/cron","")

#logging
level = "info"
levels = {'critical': logging.CRITICAL,'error': logging.ERROR,'warning': logging.WARNING,'info': logging.INFO,'debug': logging.DEBUG}
stream_handler = logging.StreamHandler()
stream_handler.setLevel(levels[level])
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',datefmt='%d.%m.%Y %H:%M:%S',level=levels[level],handlers=[RotatingFileHandler(maxBytes=10000000,backupCount=5,filename=f"{path}/logs/network.log"),stream_handler])
logger = logging.getLogger()

latency = Latency(path,logger)
bird = Bird(path,logger)

def readPipe(messagesQueue,last=""):
    if not os.path.exists(f"{path}/pipe"): 
        print(f"Creating pipe {path}/pipe")
        os.mkfifo(f"{path}/pipe")
    while True:
        with open(f'{path}/pipe', 'r') as f:
            time.sleep(0.1)
            data = f.read()
            if data and data != last: 
                messagesQueue.put(data)
                last = data

messagesQueue = queue.Queue()
pipeThread = threading.Thread(target=readPipe, args=(messagesQueue,))
pipeThread.start()

pathToLinks,links = f'{path}/links/',[]

skip,skipUntil = 0,0
restartCooldown = regenCooldown = int(time.time()) + 1800

total, used, free = shutil.disk_usage("/")
usagePercent = (used / total) * 100
logger.info(f"Current disk space usage {round(usagePercent,1)}%")
if usagePercent > 90: logger.warning("If you hit 98%, wg-mesh will stop writing any files.")

while True:
    for runs in range(6):
        currentLinks = os.listdir(pathToLinks)
        #filter out specific links
        currentLinks = [x for x in currentLinks if bird.filter(x)]
        if links != currentLinks:
            logger.info(f"Found difference in files, triggering reload")
            difference = list(set(links) - set(currentLinks))
            logger.info(f"Difference {difference}")
            #hold until bird reports success
            if bird.bird():
                bird.mesh()
                latencyData,peers = bird.bird()
                latency.setLatencyData(latencyData,peers)
                links = currentLinks
        #every 30s
        run = [0,3]
        if runs in run:
            if links:
                logger.debug("Grabbing messages")
                messages = []
                while not messagesQueue.empty(): messages.append(messagesQueue.get())
                logger.info("Running latency")
                skip = latency.run(runs,messages)
                if skip > 0: 
                    skipUntil = time.time() + 60
                    logger.info(f"Skipping 10s wait until {skipUntil}")
                elif skip == -1 and int(time.time()) > restartCooldown:
                    logger.info(f"Triggering bird restart")
                    os.system("sudo systemctl restart bird")
                    restartCooldown = int(time.time()) + 1800
                elif skip == -2 and int(time.time()) > regenCooldown:
                    logger.info(f"Triggering bird config regenerate")
                    links.append("dummy")
                    regenCooldown = int(time.time()) + 1800
        else:
            if skipUntil < time.time(): time.sleep(10)