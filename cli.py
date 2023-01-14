#!/usr/bin/python3

from Class.cli import CLI
import sys, os

#path
path = os.path.dirname(os.path.realpath(__file__))
cli = CLI(path)

if len(sys.argv) == 1:
    print("init <name> <id>, connect <IP> <token>, disconnect")
elif sys.argv[1] == "init":
    cli.init(sys.argv[2],sys.argv[3])
elif sys.argv[1] == "connect":
    cli.connect(sys.argv[2],sys.argv[3])
elif sys.argv[1] == "disconnect":
    cli.disconnect()