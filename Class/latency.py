import subprocess, requests, json, copy, time, sys, re, os
from Class.wireguard import Wireguard
from Class.templator import Templator
from datetime import datetime
from threading import Thread
from Class.base import Base
from decimal import Decimal
from random import randint

class Latency(Base):
    Templator = Templator()

    def __init__(self,path,logger):
        super().__init__()
        self.wg = Wireguard(path)
        self.latencyData = {}
        self.logger = logger
        self.linkState = {}
        self.path = path
        self.noWait = 0
        self.lastReload = int(time.time()) + 600
        self.linkReloadReset = int(time.time()) + 3600
        self.currentLinks = self.wg.getLinks(False)
        self.config = self.readFile(f'{path}/configs/config.json')
        self.network = self.readFile(f"{path}/configs/network.json")
        if not self.network: self.network = {"created":int(time.time()),"updated":0}

    def reloadPeacemaker(self,nic,ongoing,eventCount,latency,old):
        #needs to be ongoing
        if not ongoing: return False
        #ignore links dead or nearly dead links
        if latency > 10000 and float(old) > 10000: return False
        #ignore any negative changes
        if latency <= float(old): return False
        #to keep precision we multiplied them by 10
        latency = Decimal(latency / 10)
        old = Decimal(old / 10)
        #get diff and change in percentage
        diff = Decimal(latency - Decimal(old))
        percentage = (abs(old - latency) / latency) * Decimal('100')
        self.logger.debug(f"{nic} Current percentage: {percentage}%, (current {latency}, earlier {old}, diff {diff})")
        if latency < 10 and diff >= 5:
            return True
        elif percentage >= 50:
            return True
        else:
            return False

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

    def getRecentLatencyData(self,target):
        for node in self.latencyData:
            if target == node['target']: return node 

    def getLatency(self,config,pings=4):
        targets = []
        for row in config: targets.append(row['target'])
        latency =  self.fping(targets,pings)
        if not latency:
            self.logger.warning("No pingable links found.")
            return False
        total,ongoingLoss,ongoingJitter,self.reload,self.noWait,peers = 0,0,0,[],0,[]
        for node in list(config):
            for entry,row in latency.items():
                if entry == node['target']:
                    peers.append(entry)
                    #get old latencyData before reload, so we have a better reference
                    oldLatencyData = self.getOldLatencyData(node['target'])
                    old = oldLatencyData['cost']
                    #get average
                    current = int(self.getAvrg(row) * 10)
                    if current > 65534: current = 65534
                    node['base'] = node['cost'] = current
                    if node['nic'] in self.linkState: node['cost'] += self.linkState[node['nic']]['cost']
                    if entry not in self.network: self.network[entry] = {"packetloss":{},"latency":[],"outages":0,"state":1}
                    #if latency doesn't exist in network.json create it
                    if not "latency" in self.network[entry]: self.network[entry]['latency'] = []
                    #Save raw latency values per interface
                    for ping in row: self.network[entry]['latency'].append(float(ping[0]))
                    #Keep only the last 100 records
                    self.network[entry]['latency'] = self.network[entry]['latency'][-100:]
                    #Packetloss
                    hasLoss,peakLoss = len(row) < pings -1,(pings -1) - len(row)
                    if hasLoss:
                        #keep packet loss events for 20 minutes * loss
                        self.network[entry]['packetloss'][int(time.time()) + (2100 * int(peakLoss))] = {"peak":peakLoss,"latency":current}
                        self.logger.info(f"{node['nic']} ({entry}) Packetloss detected got {len(row)} of {pings -1}")
                        #if we have loss and it isn't a dead link, set noWait
                        if len(row) > 1: self.noWait +1

                    eventCount,eventScore = self.countEvents(entry,'packetloss')
                    #multiply by 10 otherwise small package loss may not result in routing changes
                    eventScore = (eventScore * eventCount) * 10
                    if eventCount > 0:
                        node['cost'] += eventScore
                        self.logger.debug(f"Loss {node['nic']} ({entry}) Weight: {old}, Latency: {current}, Modified: {node['cost']}, Score: {eventScore}, Count: {eventCount}")
                        if self.reloadPeacemaker(node['nic'],hasLoss,eventCount,node['cost'],old): 
                            self.logger.debug(f"{node['nic']} ({entry}) Triggering Packetloss reload")
                            self.linkState[node['nic']]['reload'] += 1
                            self.reload.append(node['nic'])
                            self.noWait += 1
                        ongoingLoss += 1

                    total += 1
                    #Grab linkID
                    linkID = re.findall(f"{self.config['prefix']}.*?([0-9]+)",node['nic'], re.MULTILINE)[0]
                    #if within 200-255 range (client) adjust base cost/weight to avoid transit
                    if (int(linkID) >= 200 or int(self.config['id']) >= 200) and (node['cost'] + 1000) < 65534: node['cost'] += 1000
                    #make sure its always int
                    node['cost'] = int(round(node['cost']))
                    #make sure we stay below max int
                    if node['cost'] > 65534: node['cost'] = 65534
                    #make sure we always stay over zero
                    #in case of a typo and you connect to itself, it may cause a weight to be measured at zero
                    if node['cost'] < 0: node['cost'] = 1

        #clear out old peers
        for entry in list(self.network):
            if entry not in peers: del self.network[entry]
        self.logger.info(f"Total {total}, Packetloss {ongoingLoss}")
        self.network['updated'] = int(time.time())
        return config

    def run(self,messages=[]):
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
            latencyData = self.getLatency(copy.deepcopy(self.latencyData),5)
            if not latencyData:
                self.logger.warning("Nothing todo")
            else:
                #save in memory so we don't have to read the config file again
                self.latencyData = copy.deepcopy(latencyData)
                birdConfig = self.Templator.genBird(latencyData,self.peers,self.config)
                #write
                self.saveFile(birdConfig,'/etc/bird/bird.conf')
                nicReload = False
                #if a link triggers more than 5 reloads per hour, ignore it.
                for nic in self.reload:
                    if self.linkState[nic]['reload'] < 5: nicReload = True
                #check if we need to reset self.linkReloadReset
                if int(time.time()) > self.linkReloadReset:
                    self.linkReloadReset = int(time.time()) + 3600
                    for nic in self.linkState:
                        self.linkState[nic]['reload'] = 0
                #reload bird with updates only every 10 minutes or if reload is greater than 1
                if int(time.time()) > self.lastReload or nicReload:
                    #keep a copy with the current values in the bird config
                    self.latencyDataState = copy.deepcopy(self.latencyData)
                    #reload
                    self.logger.info(f"Reloading bird ({','.join(self.reload)})")
                    self.cmd('sudo systemctl reload bird')
                    self.lastReload = int(time.time()) + self.config['bird']['reloadInterval']
                else:
                    self.logger.debug(f"Next reload {self.lastReload}")
            #however save any packetloss detected
            self.saveFile(self.network,f"{self.path}/configs/network.json")
        return self.noWait

    def setLatencyData(self,latencyData,peers):
        #fill linkState
        for data in latencyData:
            if not data['nic'] in self.linkState: self.linkState[data['nic']] = {"cost":0,"reload":0}
        #copy dicts
        self.latencyData = copy.deepcopy(latencyData)
        self.latencyDataState = copy.deepcopy(latencyData)
        self.peers = peers

    def sendMessage(self,status,row,oldRow={}):
        linkOnDisk = self.currentLinks[f"{row['nic']}.sh"]
        mtr = ["..."]
        if status != 1:
            if linkOnDisk['remotePublic']:
                targetIP = linkOnDisk['remotePublic']
                targetIP = targetIP.replace("[","").replace("]","")
                mtr = self.cmd(f'mtr {targetIP} --report --report-cycles 3 --no-dns')
                #if the mtr fails to run, grab the error message instead
                if not mtr[0] and mtr[1]: mtr[0] = mtr[1]
            else:
                mtr = ["No public ip available for mtr",""]
        notifications = self.config['notifications']
        if status == 1:
            self.notify(notifications['gotifyUp'],f"Node {self.config['id']}: {row['nic']} is up",f"{row['nic']} has been down {self.network[row['target']]['outages']} times")
        elif status == 2:
            newLatency = round(row['base'] / 10)
            oldLatency = round(oldRow['base'] / 10)
            diff = round(newLatency - oldLatency)
            self.notify(notifications['gotifyChanges'],f"Node {self.config['id']}: {row['nic']} +{diff}ms, {oldLatency}ms to {newLatency}ms",f"{mtr[0]}")
        else:
            self.notify(notifications['gotifyDown'],f"Node {self.config['id']}: {row['nic']} is down ({self.network[row['target']]['outages']})",f"{mtr[0]}")

    def notifications(self,latencyData):
        messages = {"up":[],"down":[],"changes":[]}
        for index,row in enumerate(latencyData):
            notifications = self.config['notifications']
            oldRow = self.getRecentLatencyData(row['target'])
            diff = round((row['base'] / 10) - (oldRow['base'] / 10))
            nic = row['nic']
            if self.network[row['target']]['state']: 
                self.network[row['target']]['lastOnline'] = int(time.time())
            elif not 'lastOnline' in self.network[row['target']]:
                self.network[row['target']]['lastOnline'] = int(time.time())
            if not self.network[row['target']]['state'] and row['cost'] != 65534:
                self.network[row['target']]['state'] = 1
                self.logger.warning(f"Link {row['nic']} is up")
                #send push notifcations out only the first time and every 5th time, instead of everytime...
                if self.network[row['target']]['state'] == 1 or self.network[row['target']]['outages'] % 5 == 0 and notifications['enabled'] and notifications['gotifyUp'] and notifications['gotifyUp'] != "disabled":
                    messages['up'].append([1,copy.deepcopy(row)])
            elif self.network[row['target']]['state'] and row['cost'] == 65534:
                self.network[row['target']]['state'] = 0
                self.network[row['target']]['outages'] += 1
                self.logger.warning(f"Link {row['nic']} is down")
                #send push notifcations out only the first time and every 5th time, instead of everytime...
                if self.network[row['target']]['state'] == 1 or self.network[row['target']]['outages'] % 5 == 0 and notifications['enabled'] and notifications['gotifyDown'] and notifications['gotifyDown'] != "disabled":
                    messages['down'].append([0,copy.deepcopy(row)])
            #if the difference suddenly is bigger than or equal 20ms, trigger an mtr + ignore negative changes
            elif diff >= 20 and diff <= 2000:
                self.logger.debug(f"{nic} +{diff}ms, before {round(oldRow['base'] / 10)}ms, now {round(row['base'] / 10)}ms")
                if notifications['enabled'] and notifications['gotifyChanges'] and notifications['gotifyChanges'] != "disabled":
                    messages['changes'].append([2,copy.deepcopy(row),copy.deepcopy(oldRow)])
        #processing gotify messages
        threshold = len(latencyData) / 2
        #ignore if half of our connections report in
        if len(messages['up']) <= threshold:
            for message in messages['up']:
                sendMessage = Thread(target=self.sendMessage, args=(message))
                sendMessage.start()
        else:
            self.logger.warning(f"Skipping linkUp gotify messages {len(messages['up'])}/{threshold}")
        if len(messages['down']) <= threshold:
            for message in messages['down']:
                sendMessage = Thread(target=self.sendMessage, args=(message))
                sendMessage.start()
        else:
            self.logger.warning(f"Skipping linkDown gotify messages {len(messages['down'])}/{threshold}")
        if len(messages['changes']) <= threshold:
            for message in messages['changes']:
                sendMessage = Thread(target=self.sendMessage, args=(message))
                sendMessage.start()
        else:
            self.logger.warning(f"Skipping changes gotify messages {len(messages['changes'])}/{threshold}")

    def getConfig(self):
        return self.config