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
        #every 30s
        if runs == 0 or runs == 3:
            if links: latency.run(runs)
        else:
            time.sleep(10)