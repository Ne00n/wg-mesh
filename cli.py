#!/usr/bin/python3

from Class.cli import CLI
import sys, os

options = "init <id>, status, used, bender, migrate, recover, connect/peer <http://IP/DOMAIN:8080> <token>, tunnel, reconnect, disconnect, up, down, clean, proximity, token, disable, enable, set, cost"
#path
path = os.path.dirname(os.path.realpath(__file__))
cli = CLI(path)

if len(sys.argv) == 1:
    print(options)
elif sys.argv[1] == "init":
    state = sys.argv[3] if len(sys.argv) > 3 else "local"
    cli.init(sys.argv[2],state)
elif sys.argv[1] == "used":
    cli.used()
elif sys.argv[1] == "status":
    cli.status()
elif sys.argv[1] == "bender":
    cli.bender()
elif sys.argv[1] == "connect" or sys.argv[1] == "peer":
    if len(sys.argv) <= 2: exit("URL is missing.")
    cli.connect(sys.argv[2:])
elif sys.argv[1] == "forward":
    cli.forward(sys.argv[2])
elif sys.argv[1] == "tunnel":
    if len(sys.argv) <= 2: exit("tunnel create default/awg or tunnel delete tunnel120")
    cli.tunnel(sys.argv[2:])
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
elif sys.argv[1] == "reconnect":
    upgrade = False
    sys.argv = sys.argv[2:]
    for param in sys.argv:
        if param.lower() == "upgrade": upgrade = True
    cli.reconnect(upgrade)
elif sys.argv[1] == "up" or sys.argv[1] == "down":
    cli.links(sys.argv[1])
elif sys.argv[1] == "clean":
    ignoreEndpoint = False
    sys.argv = sys.argv[2:]
    for param in sys.argv:
        if param == "ignoreEndpoint": ignoreEndpoint = True
    cli.clean(ignoreEndpoint)
elif sys.argv[1] == "migrate":
    cli.migrate()
elif sys.argv[1] == "recover":
    cli.recover()
elif sys.argv[1] == "token":
    cli.token()
elif sys.argv[1] == "update":
    cli.update()
elif sys.argv[1] == "geo":
    cli.geo()
elif sys.argv[1] == "disable":
    sys.argv = sys.argv[2:]
    cli.disable(sys.argv)
elif sys.argv[1] == "enable":
    sys.argv = sys.argv[2:]
    cli.enable(sys.argv)
elif sys.argv[1] == "set":
    sys.argv = sys.argv[2:]
    cli.setOption(sys.argv)
elif sys.argv[1] == "cost":
    if len(sys.argv) <= 2: exit("Link missing")
    cost = None if len(sys.argv) <= 3 else int(sys.argv[3])
    cli.cost(sys.argv[2],cost)
elif sys.argv[1] == "debug":
    if len(sys.argv) <= 2: exit("Link missing")
    cli.debug(sys.argv[2])
else:
    print(options)