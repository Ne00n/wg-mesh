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

    def checkJitter(self,row,interface):
        historyRaw, history = self.network[interface]['latency'][-60:], []
        for ping in historyRaw: history.append(ping)
        #generate grace
        if len(history) >= 5:
            avrg = mean = sum(history) / len(history)
            variance = sum((x - mean) ** 2 for x in history) / len(history)
            stdDev = max(variance ** 0.5, 0.5)
            dynamicGrace = stdDev * 2
        else:
            avrg = self.getAvrg(row)
            if avrg < 20:
                gracePercent = 0.25
            elif avrg < 50:
                gracePercent = 0.20
            elif avrg < 100:
                gracePercent = 0.15
            else:
                gracePercent = 0.10
            dynamicGrace = max(avrg * gracePercent, 1.0)

        minGrace = 5
        maxGrace = 25
        #cap dynamicGrace
        dynamicGrace = max(minGrace, min(dynamicGrace, maxGrace))

        for entry in row:
            if entry[0] == "timed out": continue
            if float(entry[0]) > avrg + dynamicGrace: return True,round(float(entry[0]) - (avrg + dynamicGrace),2)
        return False,0

    def reloadPeacemaker(self,nic,ongoing,eventCount,latency,old):
        #needs to be ongoing
        if not ongoing: return False
        #ignore links dead or nearly dead links
        if latency > 20000 and float(old) > 20000: return False
        #ignore any negative changes
        if latency <= float(old): return False
        #to keep precision we multiplied them by 10
        latency = round(latency / 10,1)
        old = round(old / 10,1)
        #get diff and change in percentage
        diff = int(latency - float(old))
        percentage = round((abs(float(old) - latency) / latency) * 100.0,1)
        self.logger.debug(f"{nic} Current percentage: {percentage}%, (current {latency}, earlier {old}, diff {diff})")
        if latency < 10 and diff >= 2:
            return True
        elif latency < 20 and diff >= 3:
            return True
        elif latency < 50 and diff >= 5:
            return True
        elif latency < 100 and diff >= 10:
            return True
        elif latency > 100 and percentage >= 10:
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
                    if entry not in self.network: self.network[entry] = {"packetloss":{},"jitter":{},"latency":[],"outages":0,"state":1}
                    #if latency doesn't exist in network.json create it
                    if not "latency" in self.network[entry]: self.network[entry]['latency'] = []
                    #Save raw latency values per interface
                    for ping in row:
                        #ignore timed out
                        if ping[0] == "timed out": continue
                        self.network[entry]['latency'].append(float(ping[0]))
                    #Keep only the last 100 records
                    self.network[entry]['latency'] = self.network[entry]['latency'][-100:]
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
                    if self.config['bird']['jitter']:
                        hasJitter,peakJitter = self.checkJitter(row,entry)
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
                    node['cost'] = int(round(node['cost']))
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
            latencyData = self.getLatency(self.latencyData,5)
            if not latencyData:
                self.logger.warning("Nothing todo")
            else:
                #save in memory so we don't have to read the config file again
                self.notifications(latencyData)
                self.latencyData = copy.deepcopy(latencyData)
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
                    self.logger.debug(f"Next reload {self.lastReload}")
            #however save any packetloss or jitter detected
            self.saveJson(self.network,f"{self.path}/configs/network.json")
        return self.noWait

    def setLatencyData(self,latencyData,peers):
        #fill linkState
        for data in latencyData:
            if not data['nic'] in self.linkState: self.linkState[data['nic']] = {"state":1,"cost":0,"outages":0}
        #copy dicts
        self.latencyData = copy.deepcopy(latencyData)
        self.latencyDataState = copy.deepcopy(latencyData)
        self.peers = peers

    def sendMessage(self,status,row,diff=0):
        linkOnDisk = self.currentLinks[f"{row['nic']}.sh"]
        mtr = ["..."]
        if status != 1:
            if linkOnDisk['remotePublic']:
                targetIP = linkOnDisk['remotePublic']
                targetIP = targetIP.replace("[","").replace("]","")
                mtr = self.cmd(f'mtr {targetIP} --report --report-cycles 3 --no-dns')
            else:
                mtr = ["No public ip available for mtr",""]
        notifications = self.config['notifications']
        if status == 1:
            self.notify(notifications['gotifyUp'],f"Node {self.config['id']}: {row['nic']} is up",f"{row['nic']} has been down {self.linkState[row['nic']]['outages']} times")
        elif status == 2:
            self.notify(notifications['gotifyChanges'],f"Node {self.config['id']}: {row['nic']} {diff}ms change",f"{mtr[0]}")
        else:
            self.notify(notifications['gotifyDown'],f"Node {self.config['id']}: {row['nic']} is down ({self.linkState[row['nic']]['outages']})",f"{mtr[0]}")

    def notifications(self,latencyData):
        messages = {"up":[],"down":[],"changes":[]}
        for index,row in enumerate(latencyData):
            oldLatencyData = self.getRecentLatencyData(row['target'])
            diff = round(abs(row['cost'] - oldLatencyData['cost']) / 10)
            notifications = self.config['notifications']
            nic = row['nic']
            if not self.linkState[nic]['state'] and row['cost'] != 65535:
                self.linkState[row['nic']]['state'] = 1
                self.network[row['target']]['state'] = 1
                self.logger.warning(f"Link {row['nic']} is up")
                if notifications['enabled'] and notifications['gotifyUp'] and notifications['gotifyUp'] != "disabled":
                    messages['up'].append([1,row])
            elif self.linkState[nic]['state'] and row['cost'] == 65535:
                self.linkState[row['nic']]['state'] = 0
                self.network[row['target']]['state'] = 0
                self.linkState[row['nic']]['outages'] += 1
                self.network[row['target']]['outages'] += 1
                self.logger.warning(f"Link {row['nic']} is down")
                if notifications['enabled'] and notifications['gotifyDown'] and notifications['gotifyDown'] != "disabled":
                    messages['down'].append([0,row])
            #if the difference suddenly is bigger than or equal 20ms, trigger an mtr
            elif diff >= 20 and diff <= 2000:
                self.logger.debug(f"{nic} got {diff}ms change, before {round(row['cost'] / 10)}ms, now {round(oldLatencyData['cost'] / 10)}ms")
                if notifications['enabled'] and notifications['gotifyChanges'] and notifications['gotifyChanges'] != "disabled":
                    messages['changes'].append([2,row,diff])
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