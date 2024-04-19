import subprocess, requests, json, time, sys, re, os
from Class.wireguard import Wireguard
from Class.templator import Templator
from datetime import datetime
from Class.base import Base
from random import randint

class Latency(Base):
    Templator = Templator()

    def __init__(self,path,logger):
        self.wg = Wireguard(path)
        self.latencyData = {}
        self.logger = logger
        self.path = path
        self.config = self.readConfig(f'{path}/configs/config.json')
        self.subnetPrefixSplitted = self.config['subnet'].split(".")
        self.network = self.readConfig(f"{path}/configs/network.json")
        if not self.network: self.network = {"created":int(time.time()),"updated":0}

    def parse(self,configRaw):
        if self.config['bird']['ospfv2']:
            parsed = re.findall('interface "([a-zA-Z0-9]*)".{50,130}?cost ([0-9.]+);\s#([0-9.]+)E',configRaw, re.DOTALL)
        else:
            parsed = re.findall('interface "([a-zA-Z0-9]*)".{35,130}?cost ([0-9.]+);\s#([0-9.]+)E',configRaw, re.DOTALL)
        data = []
        for nic,weight,target in parsed:
            data.append({'nic':nic,'target':target,'weight':weight})
        return data

    def checkJitter(self,row,avrg):
        grace = 20
        for entry in row:
            if entry[0] == "timed out": continue
            if float(entry[0]) > avrg + grace: return True,round(float(entry[0]) - (avrg + grace),2)
        return False,0

    def reloadPeacemaker(self,nic,ongoing,eventCount,latency,weight):
        #needs to be ongoing
        if not ongoing: return False
        #ignore links dead or nearly dead links
        if latency > 20000 and float(weight) > 20000: return False
        #ignore any negative changes
        if latency <= float(weight): return False
        diff = latency - float(weight)
        percentage = round((abs(float(weight) - latency) / latency) * 100.0,1)
        #needs to be higher than 15% and 20+ difference
        self.logger.info(f"{nic} Current percentage: {percentage}%, needed 15% (latency {latency}, weight {weight}, diff {diff})")
        if diff <= 20 or percentage <= 15: return False
        return True

    def countEvents(self,entry,eventType):
        eventCount,eventScore = 0,0
        for event,details in list(self.network[entry][eventType].items()):
            if int(event) > int(time.time()): 
                eventCount += 1
                eventScore += details['peak']
            #delete events after 60 minutes
            elif (int(time.time()) - 3600) > int(event):
                del self.network[entry][eventType][event]
        return eventCount,round(eventScore,1)

    def getLatency(self,config,pings=4):
        targets = []
        for row in config: targets.append(row['target'])
        latency =  self.fping(targets,pings,True)
        if not latency:
            self.logger.warning("No pingable links found.")
            return False
        total,ongoingLoss,ongoingJitter,self.reload,self.noWait,peers = 0,0,0,0,0,[]
        for node in list(config):
            for entry,row in latency.items():
                if entry == node['target']:
                    peers.append(entry)
                    node['cost'] = node['current'] = self.getAvrg(row,False)
                    if entry not in self.network: self.network[entry] = {"packetloss":{},"jitter":{}}

                    #Packetloss
                    hasLoss,peakLoss = len(row) < pings -1,(pings -1) - len(row)
                    if hasLoss:
                        #keep packet loss events for 15 minutes
                        self.network[entry]['packetloss'][int(time.time()) + randint(900,1200)] = {"peak":peakLoss,"latency":node['current']}
                        self.logger.info(f"{node['nic']} ({entry}) Packetloss detected got {len(row)} of {pings -1}")

                    eventCount,eventScore = self.countEvents(entry,'packetloss')
                    #multiply by 10 otherwise small package loss may not result in routing changes
                    eventScore = (eventScore * eventCount) * 10
                    if eventCount > 0:
                        node['cost'] += eventScore
                        self.logger.debug(f"Loss {node['nic']} ({entry}) Weight: {node['weight']}, Latency: {node['current']}, Modified: {node['cost']}, Score: {eventScore}, Count: {eventCount}")
                        if self.reloadPeacemaker(node['nic'],hasLoss,eventCount,node['cost'],node['weight']): 
                            self.logger.debug(f"{node['nic']} ({entry}) Triggering Packetloss reload")
                            self.reload += 1
                            self.noWait += 1
                        ongoingLoss += 1

                    #Jitter
                    hasJitter,peakJitter = self.checkJitter(row,self.getAvrg(row))
                    if hasJitter:
                        #keep jitter events for 30 minutes
                        self.network[entry]['jitter'][int(time.time()) + randint(1700,2100)] = {"peak":peakJitter,"latency":node['current']}
                        self.logger.info(f"{node['nic']} ({entry}) High Jitter dectected")

                    eventCount,eventScore = self.countEvents(entry,'jitter')
                    if eventCount > 0:
                        node['cost'] += eventScore
                        self.logger.debug(f"Jitter {node['nic']} ({entry}) Weight: {node['weight']}, Latency: {node['current']}, Modified: {node['cost']}, Score: {eventScore}, Count: {eventCount}")
                        if self.reloadPeacemaker(node['nic'],hasJitter,eventCount,node['cost'],node['weight']):
                            self.logger.debug(f"{node['nic']} ({entry}) Triggering Jitter reload")
                            self.reload += 1
                        ongoingJitter += 1

                    total += 1
                    #if within 200-255 range (client) adjust base cost/weight to avoid transit
                    linkID = re.findall(f"{self.config['prefix']}.*?([0-9]+)",node['nic'], re.MULTILINE)[0]
                    if (int(linkID) >= 200 or int(self.config['id']) >= 200) and (node['cost'] + 10000) < 65535: node['cost'] += 10000
                    #make sure its always int
                    node['cost'] = int(node['cost'])
                    #make sure we stay below max int
                    if node['cost'] > 65535: node['cost'] = 65535
                    #make sure we always stay over zero
                    #in case of a typo and you connect to itself, it may cause a weight to be measured at zero
                    if node['cost'] < 0: node['cost'] = 1

        #clear out old peers
        for entry in list(self.network):
            if entry not in peers: del self.network[entry]
        self.logger.info(f"Total {total}, Jitter {ongoingJitter}, Packetloss {ongoingLoss}")
        self.network['updated'] = int(time.time())
        return config

    def run(self,runs):
        #Check if bird is running
        self.logger.debug("Checking bird status")
        bird = self.cmd("systemctl status bird")[0]
        if not "running" in bird:
            self.logger.warning("bird not running")
            return -1
        #Getting config
        self.logger.debug("Reading bird config")
        configRaw = self.cmd("cat /etc/bird/bird.conf")[0].rstrip()
        #Parsing
        config = self.parse(configRaw)
        print(config)
        if not config:
            self.logger.warning("Parsed bird config is empty")
            return -2
        #fping
        self.logger.debug("Running fping")
        latencyData = self.getLatency(config,5)
        print(latencyData)
        if not latencyData:
            self.logger.warning("Nothing todo")
        else:
            latencyData = self.wg.groupByArea(latencyData)
            birdConfig = self.Templator.genBird(latencyData,self.peers,self.config)
            #write
            self.saveFile(birdConfig,'/etc/bird/bird.conf')
            #reload bird with updates only every 10 minutes or if reload is greater than 1
            restart = [0,10,20,30,40,50]
            if (datetime.now().minute in restart and runs == 0) or self.reload > 0:
                #reload
                self.logger.info("Reloading bird")
                self.cmd('sudo systemctl reload bird')
            else:
                self.logger.debug(f"{datetime.now().minute} not in window.")
        #however save any packetloss or jitter detected
        self.saveJson(self.network,f"{self.path}/configs/network.json")
        time.sleep(5)
        return self.noWait

    def setLatencyData(self,latencyData,peers):
        self.latencyData = latencyData
        self.peers = peers