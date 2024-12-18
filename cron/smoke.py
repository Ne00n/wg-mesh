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
    resp = wireguard.AskProtocol(f'http://{target}:8080','')
    if not "geo" in resp: 
        print(f"No geo from {target}")
        continue
    if not resp: 
        print(f"No response from {target}")
        continue
    data[target] = resp

sortedData = dict(sorted(data.items(), key=lambda item: item[1]['geo']['country']))

build = {}
for target,data in sortedData.items():
    if not data['geo']['continent'] in build: build[data['geo']['continent']] = {}
    if not data['geo']['city'] in build[data['geo']['continent']]: build[data['geo']['continent']][data['geo']['city']] = []
    build[data['geo']['continent']][data['geo']['city']].append([target,data['geo']['countryCode']])

smokeping = """

*** Targets ***

probe = FPing

menu = Top
title = Network Latency Grapher
remark = Welcome to the SmokePing website of xxx Company. Here you will learn all about the latency of our network.

"""

for continent,details in build.items():
    continent = continent.replace(" ","")
    smokeping += f"""

+ {continent}
menu = {continent}
title = {continent}

"""
    for city, data in details.items():
        id = data[0][0].split(".")[2:3][0]
        smokeping += f"""
++ {data[0][1]}{id}

menu = {data[0][1]}{id} | {city}
title = {data[0][1]}{id} | {city}
host = {data[0][0]}
alerts = startloss,someloss,bigloss,rttdetect,hostdown,lossdetect
"""

base.saveFile(smokeping,"/etc/smokeping/config.d/Targets")