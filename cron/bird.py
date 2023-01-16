#!/usr/bin/python3
import time, sys, os
sys.path.append("..") # Adds higher directory to python modules path.
from Class.bird import Bird

bird = Bird()

path = os.path.dirname(os.path.realpath(__file__))
path = f'{path}/links/'.replace("/cron","")
links = os.listdir(path)
bird.bird()

while True:
    currentLinks = os.listdir(path)
    if links != currentLinks:
        bird.bird()
        links = currentLinks
    time.sleep(60)
