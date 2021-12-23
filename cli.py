#!/usr/bin/python3

from Class.wireguard import Wireguard
from Class.bird import Bird
import sys, os

wg = Wireguard()
bird = Bird()

if os.geteuid() != 0: exit("You need to run this as root")

if len(sys.argv) == 1:
    print("init <name> <id>, join <name>, bird")
elif sys.argv[1] == "init":
    wg.init(sys.argv[2],sys.argv[3])
elif sys.argv[1] == "join":
    wg.join(sys.argv[2])
elif sys.argv[1] == "bird":
    bird.bird()
elif sys.argv[1] == "connect":
    wg.connect(sys.argv[2:])