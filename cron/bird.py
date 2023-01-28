#!/usr/bin/python3
import time, sys, os
sys.path.append("..") # Adds higher directory to python modules path.
from Class.latency import Latency
from Class.bird import Bird

path = os.path.dirname(os.path.realpath(__file__))
path = path.replace("/cron","")

latency = Latency(path)
bird = Bird(path)

path,links = f'{path}/links/',[]

runs = 0
while True:
    currentLinks = os.listdir(path)
    if links != currentLinks:
        #hold until bird reports success
        if bird.bird():
            bird.mesh()
            bird.bird()
            links = currentLinks
    #every 5 minutes / 30 runs we do run latency
    if runs == 30:
        if links: latency.run()
        runs = 0
    time.sleep(10)
    runs += 1