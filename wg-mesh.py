#!/usr/bin/python3

from Class.wireguard import Wireguard
import sys, os

wg = Wireguard()

if os.geteuid() != 0:
    print("You need to run this as root")
    exit()

if len(sys.argv) == 1:
    print("join <name>")
elif sys.argv[1] == "join":
    wg.join(sys.argv[2])