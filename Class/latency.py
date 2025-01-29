import subprocess, requests, json, copy, time, sys, re, os
from Class.wireguard import Wireguard
from Class.templator import Templator
from datetime import datetime
from threading import Thread
from Class.base import Base
from random import randint

class Latency(Base):
    Templator = Templator()

    def __init__(self,path,logger):
        self.wg = Wireguard(path)
        self.latencyData = {}
        self.logger = logger
        self.linkState = {}
        self.path = path
        self.noWait = 0
        self.lastReload = int(time.time()) + 600
        self.currentLinks = self.wg.getLinks(False)
        self.config = self.readJson(f'{path}/configs/config.json')
        self.subnetPrefixSplitted = self.config['subnet'].split(".")
        self.network = self.readJson(f"{path}/configs/network.json")
        if not self.network: self.network = {"created":int(time.time()),"updated":0}

    def checkJitter(self,row,avrg):
        grace = 20
        for entry in row:
            if entry[0] == "timed out": continue
            if float(entry[0]) > avrg + grace: return True,round(float(entry[0]) - (avrg + grace),2)
        return False,0

    def reloadPeacemaker(self,nic,ongoing,eventCount,latency,old):
        #needs to be ongoing
        if not ongoing: return False
        #ignore links dead or nearly dead links
        if latency > 20000 and float(old) > 20000: return False
        #ignore any negative changes
        if latency <= float(old): return False
        diff = latency - float(old)
        percentage = round((abs(float(old) - latency) / latency) * 100.0,1)
        #needs to be higher than 15% and 20+ difference
        self.logger.info(f"{nic} Current percentage: {percentage}%, needed 15% (current {latency}, earlier {old}, diff {diff})")
        if percentage <= 15: return False
        return True

    def countEvents(self,entry,eventType):
        eventCount,eventScore = 0,0
        for event,details in list(self.network[entry][eventType].items()):
            if int(event) > int(time.time()): 
                eventCount += 1
                eventScore += details['peak']
            #delete events after 120 minutes
            elif (int(time.time()) - 7200) > int(event):
                del self.network[entry][eventType][event]
        return eventCount,round(eventScore,1)

    def getOldLatencyData(self,target):
        for node in self.latencyDataState:
            if target == node['target']: return node 

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
                    #get old latencyData before reload, so we have a better reference
                    oldLatencyData = self.getOldLatencyData(node['target'])
                    old = oldLatencyData['cost']
                    #get average
                    node['cost'] = current = self.getAvrg(row,False)
                    if node['nic'] in self.linkState: node['cost'] += self.linkState[node['nic']]['cost']
                    if entry not in self.network: self.network[entry] = {"packetloss":{},"jitter":{}}
                    #Packetloss
                    hasLoss,peakLoss = len(row) < pings -1,(pings -1) - len(row)
                    if hasLoss:
                        #keep packet loss events for 30 minutes
                        self.network[entry]['packetloss'][int(time.time()) + randint(1700,2100)] = {"peak":peakLoss,"latency":current}
                        self.logger.info(f"{node['nic']} ({entry}) Packetloss detected got {len(row)} of {pings -1}")

                    eventCount,eventScore = self.countEvents(entry,'packetloss')
                    #multiply by 10 otherwise small package loss may not result in routing changes
                    eventScore = (eventScore * eventCount) * 10
                    if eventCount > 0:
                        node['cost'] += eventScore
                        self.logger.debug(f"Loss {node['nic']} ({entry}) Weight: {old}, Latency: {current}, Modified: {node['cost']}, Score: {eventScore}, Count: {eventCount}")
                        if self.reloadPeacemaker(node['nic'],hasLoss,eventCount,node['cost'],old): 
                            self.logger.debug(f"{node['nic']} ({entry}) Triggering Packetloss reload")
                            self.reload += 1
                            self.noWait += 1
                        ongoingLoss += 1

                    #Jitter
                    hasJitter,peakJitter = self.checkJitter(row,self.getAvrg(row))
                    if hasJitter:
                        #keep jitter events for 30 minutes
                        self.network[entry]['jitter'][int(time.time()) + randint(1700,2100)] = {"peak":peakJitter,"latency":current}
                        self.logger.info(f"{node['nic']} ({entry}) High Jitter dectected")

                    eventCount,eventScore = self.countEvents(entry,'jitter')
                    if eventCount > 0:
                        node['cost'] += eventScore
                        self.logger.debug(f"Jitter {node['nic']} ({entry}) Weight: {old}, Latency: {current}, Modified: {node['cost']}, Score: {eventScore}, Count: {eventCount}")
                        if self.reloadPeacemaker(node['nic'],hasJitter,eventCount,node['cost'],old):
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

    def run(self,runs,messages=[]):
        #Check if bird is running
        self.logger.debug("Checking bird status")
        bird = self.cmd("systemctl status bird")[0]
        if not "running" in bird:
            self.logger.warning("bird not running")
            return -1
        if self.config['operationMode'] == 0:
            self.logger.info("Running latency")
            self.logger.debug("Processing messages")
            for rawMessage in messages:
                message = json.loads(rawMessage)
                self.logger.info(f"{message['link']} set cost to {message['cost']}")
                self.linkState[message['link']]['cost'] = message['cost']
                #reset lastReload to trigger a reload, otherwise we have to wait up to 10 minutes
                self.lastReload = int(time.time())
            self.logger.debug("Running fping")
            latencyData = self.getLatency(self.latencyData,5)
            if not latencyData:
                self.logger.warning("Nothing todo")
            else:
                #save in memory so we don't have to read the config file again
                self.notifications(latencyData)
                self.latencyData = latencyData
                latencyData = self.wg.groupByArea(latencyData)
                birdConfig = self.Templator.genBird(latencyData,self.peers,self.config)
                #write
                self.saveFile(birdConfig,'/etc/bird/bird.conf')
                #reload bird with updates only every 10 minutes or if reload is greater than 1
                if int(time.time()) > self.lastReload or self.reload > 0:
                    #keep a copy with the current values in the bird config
                    self.latencyDataState = copy.deepcopy(self.latencyData)
                    #reload
                    self.logger.info("Reloading bird")
                    self.cmd('sudo systemctl reload bird')
                    self.lastReload = int(time.time()) + self.config['bird']['reloadInterval']
                else:
                    self.logger.debug(f"{datetime.now().minute} not in window.")
            #however save any packetloss or jitter detected
            self.saveJson(self.network,f"{self.path}/configs/network.json")
            time.sleep(5)
        else:
            time.sleep(10)
        return self.noWait

    def setLatencyData(self,latencyData,peers):
        #fill linkState
        for data in latencyData:
            if not data['nic'] in self.linkState: self.linkState[data['nic']] = {"state":1,"cost":0,"outages":0}
        #copy dicts
        self.latencyData = copy.deepcopy(latencyData)
        self.latencyDataState = copy.deepcopy(latencyData)
        self.peers = peers

    def sendMessage(self,status,row):
        linkOnDisk = self.currentLinks[f"{row['nic']}.sh"]
        mtr = ["..."]
        if status == 0:
            if linkOnDisk['remotePublic']:
                targetIP = linkOnDisk['remotePublic']
                targetIP = targetIP.replace("[","").replace("]","")
                mtr = self.cmd(f'mtr {targetIP} --report --report-cycles 3 --no-dns')
            else:
                mtr = ["No public ip available for mtr",""]
        notifications = self.config['notifications']
        if status:
            self.notify(notifications['gotifyUp'],f"Node {self.config['id']}: {row['nic']} is up",f"{row['nic']} has been down {self.linkState[row['nic']]['outages']} times")
        else:
            self.notify(notifications['gotifyDown'],f"Node {self.config['id']}: {row['nic']} is down ({self.linkState[row['nic']]['outages']})",f"{mtr[0]}")

    def notifications(self,latencyData):
        for index,row in enumerate(latencyData):
            nic = row['nic']
            if not self.linkState[nic]['state'] and row['cost'] != 65535:
                self.linkState[row['nic']]['state'] = 1
                self.logger.warning(f"Link {row['nic']} is up")
                notifications = self.config['notifications']
                if notifications['enabled']:
                    sendMessage = Thread(target=self.sendMessage, args=([1,row]))
                    sendMessage.start()
            elif self.linkState[nic]['state'] and row['cost'] == 65535:
                self.linkState[row['nic']]['state'] = 0
                self.linkState[row['nic']]['outages'] += 1
                self.logger.warning(f"Link {row['nic']} is down")
                notifications = self.config['notifications']
                if notifications['enabled']:
                    sendMessage = Thread(target=self.sendMessage, args=([0,row]))
                    sendMessage.start()