import random, time, json, re, os
from Class.wireguard import Wireguard
from Class.network import Network
from Class.base import Base

class Monitor(Base):

    def __init__(self,path,logger):
        self.logger = logger
        super().__init__()
        self.path = path
        self.history = {}
        self.toMonitor = ["packets"]
        self.threshold = 0.3

    def getNetDev(self):
        response = []
        mapping = {0:"interface",1:"bytes",2:"packets",3:"errs",4:"drop",5:"fifo",6:"frame",7:"compressed",8:"multicast",
                   9:"bytes",10:"packets",11:"errs",12:"drop",13:"fifo",14:"colls",15:"carrier",16:"compressed"}
        for line in open("/proc/net/dev"):
            if not ":" in line: continue
            line = line.rstrip().split()
            stats, interface = {}, ""
            for index, element in enumerate(line):
                if index == 0: 
                    interface = element
                    stats = {"interface":interface,"RX":{},"TX":{}}
                else:
                    category = "RX" if index < 8 else "TX"
                    stats[category][mapping[index]] = element
            response.append(stats)
        return response

    def run(self):
        interfaces = self.getNetDev()
        for stats in interfaces:
            interface = stats['interface']
            current = int(time.time())
            if not interface in self.history: self.history[interface] = {"RX":{},"TX":{}}
            for key,value in stats['RX'].items():
                if key in self.toMonitor:
                    if not key in self.history[interface]['RX']: 
                        self.history[interface]['RX'][key] = {"stats":[]}
                        self.history[interface]['RX'][key]['stats'].append({"current":value,"timestamp":current})
                    else:
                        self.history[interface]['RX'][key]['stats'].append({"current":value,"timestamp":current})
                        #keep the last 30s
                        self.history[interface]['RX'][key]['stats'] = self.history[interface]['RX'][key]['stats'][-15:]
                        lowest, highest, last = None, None, 0
                        for entry in self.history[interface]['RX'][key]['stats']:
                            diff = int(entry['current']) - last
                            if lowest is None or diff < lowest:
                                lowest = diff
                            if highest is None or diff > highest:
                                highest = diff
                        precentage = round((highest - lowest) / lowest * 100,1)
                        last = int(entry['current'])
                        if precentage >= self.threshold:
                            self.logger.warning(f"Interface {interface} reached {precentage * 100}% on RX {key} with diff {diff}")