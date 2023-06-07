#!/usr/bin/python3

from Class.cli import CLI
import sys, os

#path
path = os.path.dirname(os.path.realpath(__file__))
cli = CLI(path)

if len(sys.argv) == 1:
    print("init <id>, connect <IP> <token>, disconnect, up, down")
elif sys.argv[1] == "init":
    state = sys.argv[3] if len(sys.argv) > 3 else "local"
    cli.init(sys.argv[2],state)
elif sys.argv[1] == "connect":
    cli.connect(sys.argv[2],sys.argv[3])
elif sys.argv[1] == "optimize":
    links = sys.argv[2] if len(sys.argv) == 3 else []
    cli.optimize(links)
elif sys.argv[1] == "disconnect":
    force = True if len(sys.argv) == 3 and sys.argv[2] == "force" or len(sys.argv) == 4 and sys.argv[3] == "force" else False
    link = sys.argv[2] if len(sys.argv) == 3 and sys.argv[2] != "force" else ""
    cli.disconnect(force,link)
elif sys.argv[1] == "up":
    cli.links("up")
elif sys.argv[1] == "down":
    cli.links("down")