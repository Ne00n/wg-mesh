#!/usr/bin/python3
import logging, random, signal, time, sys, os
sys.path.append("..") # Adds higher directory to python modules path.
from logging.handlers import RotatingFileHandler
from Class.monitor import Monitor
import systemd.daemon

path = os.path.dirname(os.path.realpath(__file__))
path = path.replace("/cron","")

#logging
level = "info"
levels = {'critical': logging.CRITICAL,'error': logging.ERROR,'warning': logging.WARNING,'info': logging.INFO,'debug': logging.DEBUG}
stream_handler = logging.StreamHandler()
stream_handler.setLevel(levels[level])
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',datefmt='%d.%m.%Y %H:%M:%S',level=levels[level],handlers=[RotatingFileHandler(maxBytes=10000000,backupCount=5,filename=f"{path}/logs/monitor.log"),stream_handler])
logger = logging.getLogger()

shutdown = False
def gracefulExit(signal_number,stack_frame):
    systemd.daemon.notify('STOPPING=1')
    logger.info(f"Stopping")
    global shutdown
    shutdown = True

signal.signal(signal.SIGINT, gracefulExit)
signal.signal(signal.SIGTERM, gracefulExit)
systemd.daemon.notify('READY=1')

monitor = Monitor(path,logger)
logger.info(f"Ready")

interval = 5
while not shutdown:
    monitor.run(interval)
    time.sleep(interval)