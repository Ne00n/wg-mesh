#!/usr/bin/python3

from Class.wireguard import Wireguard
from Class.bird import Bird
import sys, os

#path
path = os.path.dirname(os.path.realpath(__file__))

if len(sys.argv) == 1:
    print("init <name> <id>")
elif sys.argv[1] == "init":
    wg = Wireguard(path,True)
    wg.init(sys.argv[2],sys.argv[3])
elif sys.argv[1] == "connect":
    wg = Wireguard(path)
    wg.connect(sys.argv[2],sys.argv[3])
elif sys.argv[1] == "disconnect":
    wg = Wireguard(path)
    wg.disconnect()