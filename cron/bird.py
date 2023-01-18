#!/usr/bin/python3
import time, sys, os
sys.path.append("..") # Adds higher directory to python modules path.
from Class.bird import Bird

path = os.path.dirname(os.path.realpath(__file__))
path = path.replace("/cron","")

bird = Bird(path)
bird.bird()
bird.mesh()

path = f'{path}/links/'
links = os.listdir(path)

while True:
    currentLinks = os.listdir(path)
    if links != currentLinks:
        bird.bird()
        bird.mesh()
        links = currentLinks
    time.sleep(30)
