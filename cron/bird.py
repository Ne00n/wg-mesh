#!/usr/bin/python3
import time, sys
sys.path.append("..") # Adds higher directory to python modules path.
from Class.bird import Bird

bird = Bird()

while True:
    bird.bird()
    time.sleep(60)
