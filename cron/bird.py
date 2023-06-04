#!/usr/bin/python3
import logging, time, sys, os
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
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',datefmt='%H:%M:%S',level=levels[level],handlers=[RotatingFileHandler(maxBytes=10000000,backupCount=5,filename=f"{path}/logs/network.log"),stream_handler])
logger = logging.getLogger()

latency = Latency(path,logger)
bird = Bird(path,logger)

path,links = f'{path}/links/',[]

while True:
    for runs in range(6):
        currentLinks = os.listdir(path)
        if links != currentLinks:
            #hold until bird reports success
            if bird.bird():
                currentLinks = os.listdir(path)
                bird.mesh()
                bird.bird()
                links = currentLinks
        #every 20s
        run = [0,2,4]
        if runs in run:
            if links: latency.run(runs)
        else:
            time.sleep(10)