#!/usr/bin/python3
import requests, time, sys, os, re
sys.path.append("..") # Adds higher directory to python modules path.
from Class.base import Base
from Class.wireguard import Wireguard

path = os.path.dirname(os.path.realpath(__file__))
path = path.replace("/cron","")

base = Base()
wireguard = Wireguard(path)

print("Getting Routes")
routes = base.cmd("birdc show route")[0]
targets = re.findall(f"(10\.0\.[0-9]+\.0\/30)",routes, re.MULTILINE)
print("Getting Connection info")
data = {}

for index, target in enumerate(targets):
    target = target.replace("0/30","1")
    print(f"Getting {index} of {len(targets) -1}")
    for run in range(1,3):
        resp = wireguard.AskProtocol(f'http://{target}:8080','')
        if resp: break
        print(f"No response from {target}")
        time.sleep(3)
    if not resp: continue
    if not "geo" in resp or not resp['geo']: 
        print(f"No geo from {target}")
        continue
    data[target] = resp

sortedData = dict(sorted(data.items(), key=lambda item: item[1]['geo']['country']))

build = {}
for target,data in sortedData.items():
    if not data['geo']['continent'] in build: build[data['geo']['continent']] = {}
    if not data['geo']['city'] in build[data['geo']['continent']]: build[data['geo']['continent']][data['geo']['city']] = []
    build[data['geo']['continent']][data['geo']['city']].append([target,data])

smokeping = """

*** Targets ***

probe = FPing

menu = Top
title = Network Latency Grapher
remark = Welcome to the SmokePing website of xxx Company. Here you will learn all about the latency of our network.

+ Indirect
menu = Indirect
title = Indirect

"""

for continent,details in build.items():
    continent = continent.replace(" ","")
    smokeping += f"""

++ {continent}
menu = {continent}
title = {continent}

"""
    for city, nodes in details.items():
        for node in nodes:
            id = str(node[0].split(".")[2:3][0]).zfill(3)
            smokeping += f"""
    +++ {node[1]['geo']['countryCode']}{id}

    menu = {node[1]['geo']['countryCode']}{id} | {city}
    title = {node[1]['geo']['countryCode']}{id} | {city}
    host = {node[0]}
    """

smokeping += """

+ Direct
menu = Direct
title = Direct

"""

for continent,details in build.items():
    continent = continent.replace(" ","")
    smokeping += f"""

++ {continent}
menu = {continent}
title = {continent}

"""
    for city, nodes in details.items():
        for node in nodes:
            id = str(node[0].split(".")[2:3][0]).zfill(3)
            host = node[1]['connectivity']['ipv4'] if node[1]['connectivity']['ipv4'] else node[1]['connectivity']['ipv6']
            smokeping += f"""
    +++ {node[1]['geo']['countryCode']}{id}

    menu = {node[1]['geo']['countryCode']}{id} | {city}
    title = {node[1]['geo']['countryCode']}{id} | {city}
    host = {host}
    """

base.saveFile(smokeping,"/etc/smokeping/config.d/wgmesh")