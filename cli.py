#!/usr/bin/python3

from Class.cli import CLI
import sys, os

#path
path = os.path.dirname(os.path.realpath(__file__))
cli = CLI(path)

if len(sys.argv) == 1:
    print("init <id>, migrate, connect <http://IP/DOMAIN:8080> <token>, disconnect, up, down, clean, proximity, token, disable, enable, set")
elif sys.argv[1] == "init":
    state = sys.argv[3] if len(sys.argv) > 3 else "local"
    cli.init(sys.argv[2],state)
elif sys.argv[1] == "connect":
    linkType = "default" if len(sys.argv) == 4 else sys.argv[4]
    port = 51820 if len(sys.argv) == 5 else sys.argv[5]
    cli.connect(sys.argv[2],sys.argv[3],linkType,port)
elif sys.argv[1] == "proximity":
    cutoff = sys.argv[2] if len(sys.argv) == 3 else 0
    cli.proximity(cutoff)
elif sys.argv[1] == "disconnect":
    force,links = False,[]
    sys.argv = sys.argv[2:]
    for param in sys.argv:
        if param.lower() == "force": force = True
        if param.lower() != "force": links.append(param)
    cli.disconnect(links,force)
elif sys.argv[1] == "up":
    cli.links("up")
elif sys.argv[1] == "down":
    cli.links("down")
elif sys.argv[1] == "clean":
    cli.clean()
elif sys.argv[1] == "migrate":
    cli.migrate()
elif sys.argv[1] == "token":
    cli.token()
elif sys.argv[1] == "update":
    cli.update()
elif sys.argv[1] == "disable":
    sys.argv = sys.argv[2:]
    cli.disable(sys.argv)
elif sys.argv[1] == "enable":
    sys.argv = sys.argv[2:]
    cli.enable(sys.argv)
elif sys.argv[1] == "set":
    sys.argv = sys.argv[2:]
    cli.setOption(sys.argv)