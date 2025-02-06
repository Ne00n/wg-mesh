#!/usr/bin/python3
import logging, time, sys, os
sys.path.append("..") # Adds higher directory to python modules path.
from logging.handlers import RotatingFileHandler
from Class.diag import Diag

path = os.path.dirname(os.path.realpath(__file__))
path = path.replace("/cron","")

#logging
level = "info"
levels = {'critical': logging.CRITICAL,'error': logging.ERROR,'warning': logging.WARNING,'info': logging.INFO,'debug': logging.DEBUG}
stream_handler = logging.StreamHandler()
stream_handler.setLevel(levels[level])
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',datefmt='%d.%m.%Y %H:%M:%S',level=levels[level],handlers=[RotatingFileHandler(maxBytes=10000000,backupCount=5,filename=f"{path}/logs/diagnostic.log"),stream_handler])
logger = logging.getLogger()

diag = Diag(path,logger)
while True:
    #check for lock file
    if os.path.isfile(f"{path}/cron/lock"): 
        time.sleep(60)
        continue
    #we need a lock file, since roatate and diag could conflict with each other
    os.open(f"{path}/cron/lock", os.O_CREAT | os.O_EXCL)
    diag.run()
    #clear lock file
    os.unlink(f"{path}/cron/lock")
    time.sleep(7200)