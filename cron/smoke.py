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
for target in targets:
    target = target.replace("0/30","1")
    resp = wireguard.AskProtocol(f'http://{target}:8080','')
    if not resp: continue
    data[target] = resp['connectivity']['ipv4']

build = {}
print("Fetching IP info")
for localIP,externalIP in data.items():
    resp = requests.get(url=f"http://ip-api.com/json/{externalIP}?fields=continent,country,city,countryCode,region")
    data = resp.json()
    if not data['continent'] in build: build[data['continent']] = {}
    if not data['city'] in build[data['continent']]: build[data['continent']][data['city']] = []
    build[data['continent']][data['city']].append([localIP,externalIP,data['countryCode']])
    time.sleep(2)

smokeping = """

*** Targets ***

probe = FPing

menu = Top
title = Network Latency Grapher
remark = Welcome to the SmokePing website of xxx Company. Here you will learn all about the latency of our network.

"""

for continent,details in build.items():
    smokeping += f"""

+ {continent}
menu = {continent}
title = {continent}

"""
    for city, data in details.items():
        id = data[0][0].split(".")[2:3][0]
        smokeping += f"""
++ {data[0][2]}{id}

menu = {data[0][2]}{id} | {city}
title = {data[0][2]}{id} | {city}
host = {data[0][0]}
alerts = startloss,someloss,bigloss,rttdetect,hostdown,lossdetect
"""

base.saveFile(smokeping,"Targets")