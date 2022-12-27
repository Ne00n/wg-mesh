#!/usr/bin/python3

from Class.wireguard import Wireguard
from Class.bird import Bird
import sys, os

if len(sys.argv) == 1:
    print("init <name> <id>")
elif sys.argv[1] == "init":
    wg = Wireguard(True)
    wg.init(sys.argv[2],sys.argv[3])
elif sys.argv[1] == "connect":
    wg = Wireguard()
    wg.connect(sys.argv[2],sys.argv[3])
elif sys.argv[1] == "disconnect":
    wg = Wireguard()
    wg.disconnect()