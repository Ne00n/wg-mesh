#!/usr/bin/python3

from Class.wireguard import Wireguard
from Class.bird import Bird
import sys, os

wg = Wireguard()
bird = Bird()

if os.geteuid() != 0: exit("You need to run this as root")

if len(sys.argv) == 1:
    print("init <name> <id>, join <name>, bird, shutdown, startup, clean")
elif sys.argv[1] == "init":
    wg.init(sys.argv[2],sys.argv[3])
elif sys.argv[1] == "join":
    wg.join(sys.argv[2])
elif sys.argv[1] == "bird":
    bird.bird()
elif sys.argv[1] == "clean":
    wg.clean()
elif sys.argv[1] == "connect":
    wg.connect(sys.argv[2],sys.argv[3],sys.argv[4],sys.argv[5],sys.argv[6],sys.argv[7],sys.argv[8])
elif sys.argv[1] == "shutdown":
    wg.shutdown()
elif sys.argv[1] == "startup":
    wg.startup()