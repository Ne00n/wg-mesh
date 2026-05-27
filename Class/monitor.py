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
        self.thresholdPercentage = 200

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

    def run(self,interval):
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
                        self.history[interface]['RX'][key]['stats'] = self.history[interface]['RX'][key]['stats'][-12:]
                        avrg, last = 0, 0
                        for entry in self.history[interface]['RX'][key]['stats']:
                            if last == 0: 
                                last = int(entry['current'])
                                continue
                            diff = int(entry['current']) - last
                            last = int(entry['current'])
                            avrg += diff
                        avrg = avrg / len(self.history[interface]['RX'][key]['stats'])
                        if diff == 0 or avrg == 0: continue
                        precentage = round((diff - avrg) / avrg * 100,1)
                        if precentage >= self.thresholdPercentage and diff > 1000:
                            self.logger.warning(f"Interface {interface} reached {precentage}% on RX {key} with diff {diff / interval}/s")