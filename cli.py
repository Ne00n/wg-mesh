#!/usr/bin/python3

from Class.wireguard import Wireguard
from Class.bird import Bird
import sys, os

wg = Wireguard()

if len(sys.argv) == 1:
    print("init <name> <id>")
elif sys.argv[1] == "init":
    wg.init(sys.argv[2],sys.argv[3])