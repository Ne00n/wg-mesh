import subprocess, requests, json, time, sys, re, os
from datetime import datetime
from Class.base import Base
from random import randint

class Latency(Base):
    def __init__(self,path,logger):
        self.logger = logger
        self.path = path
        file = f"{path}/configs/network.json"
        self.network = self.readConfig(file)
        if not self.network: self.network = {"created":int(datetime.now().timestamp()),"updated":0}

    def parse(self,configRaw):
        parsed = re.findall('interface "([a-zA-Z0-9]{3,}?)".{50,170}?cost ([0-9.]+);\s#([0-9.]+)',configRaw, re.DOTALL)
        #filter double entries
        parsed = list(set(parsed))
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

    def reloadPeacemaker(self,ongoing,eventDiff,latency,weight):
        #needs to be ongoing
        if not ongoing: return False
        #ignore links dead or nearly dead links
        if latency > 10000 and float(weight) > 10000: return False
        #ignore eventScore 1
        if latency == float(weight): return False
        diff = latency - float(weight)
        #ignore any negative changes
        if diff <= 0: return False
        percentage = round(latency / float(weight),2)
        if eventDiff > 0 and percentage < 10: return False
        return True

    def countEvents(self,entry,eventType):
        eventCount,eventScore = 0,0
        for event,details in list(self.network[entry][eventType].items()):
            if int(event) > int(datetime.now().timestamp()): 
                eventCount += 1
                if type(details) == dict:
                    eventScore = details['peak']
                else:
                    eventScore += details
            #delete events after 15 minutes
            elif (int(datetime.now().timestamp()) - 900) > int(event):
                del self.network[entry][eventType][event]
        return eventCount,eventScore

    def getLatency(self,config,pings=4):
        targets = []
        for row in config: targets.append(row['target'])
        latency =  self.fping(targets,pings,True)
        if not latency:
            self.logger.warning("No pingable links found.")
            return False
        for entry,row in latency.items():
            #drop the first ping result
            if row: 
                del row[0]
                row.sort()
            #del row[len(row) -1] #drop the highest ping result
        total,self.hadLoss,self.hadJitter,self.reload,self.noWait,peers = 0,0,0,0,0,[]
        for node in list(config):
            for entry,row in latency.items():
                if entry == node['target']:
                    peers.append(entry)
                    node['latency'] = self.getAvrg(row,False)
                    if entry not in self.network: self.network[entry] = {"packetloss":{},"jitter":{}}

                    #Packetloss
                    hasLoss,peakLoss = len(row) < pings -1,(pings -1) - len(row)
                    if hasLoss:
                        #keep event for 15 minutes
                        self.network[entry]['packetloss'][int(datetime.now().timestamp()) + 900] = {"peak":peakLoss,"latency":node['weight']}
                        self.logger.info(f"{node['nic']} ({entry}) Packetloss detected got {len(row)} of {pings -1}")

                    eventCount,eventScore = self.countEvents(entry,'packetloss')
                    threshold = 2
                    
                    if eventCount > 0: eventScore = eventScore / eventCount
                    hadLoss = True if eventCount >= threshold else False
                    eventDiff = eventCount - threshold
                    if hadLoss:
                        tmpLatency = node['latency']
                        self.logger.debug(f"{node['nic']} ({entry}) Ongoing Packetloss")
                        node['latency'] = round(node['latency'] * eventScore)
                        self.logger.debug(f"{node['nic']} ({entry}) Latency: {tmpLatency}, Modified: {node['latency']}, Score: {eventScore}, Count: {eventCount}")
                        if self.reloadPeacemaker(hasLoss,eventDiff,node['latency'],node['weight']): 
                            self.logger.debug(f"{node['nic']} ({entry}) Triggering Packetloss reload")
                            self.reload += 1
                            self.noWait += 1
                        self.hadLoss += 1

                    #Jitter
                    hasJitter,peakJitter = self.checkJitter(row,self.getAvrg(row))
                    if hasJitter:
                        #keep event for 15 minutes
                        self.network[entry]['jitter'][int(datetime.now().timestamp()) + 900] = {"peak":peakJitter,"latency":node['weight']}
                        self.logger.info(f"{node['nic']} ({entry}) High Jitter dectected")

                    eventCount,eventScore = self.countEvents(entry,'jitter')
                    threshold = 4
                    
                    if eventCount > 0: eventScore = eventScore / eventCount
                    hadJitter = True if eventCount > threshold else False
                    eventDiff = eventCount - threshold
                    if hadJitter:
                        tmpLatency = node['latency']
                        self.logger.debug(f"{node['nic']} ({entry}) Ongoing Jitter")
                        node['latency'] = round(node['latency'] * eventScore)
                        self.logger.debug(f"{node['nic']} ({entry}) Latency: {tmpLatency}, Modified: {node['latency']}, Score: {eventScore}, Count: {eventCount}")
                        if self.reloadPeacemaker(hasJitter,eventDiff,node['latency'],node['weight']):
                            self.logger.debug(f"{node['nic']} ({entry}) Triggering Jitter reload")
                            self.reload += 1
                        self.hadJitter += 1

                    total += 1
                    #make sure its always int
                    node['latency'] = int(node['latency'])
                    #make sure we stay below max int
                    if node['latency'] > 65535: node['latency'] = 65535

        #clear out old peers
        for entry in list(self.network):
            if entry not in peers: del self.network[entry]
        self.logger.info(f"Total {total}, Jitter {self.hadJitter}, Packetloss {self.hadLoss}")
        self.network['updated'] = int(datetime.now().timestamp())
        return config

    def run(self,runs):
        #Check if bird is running
        self.logger.debug("Checking bird status")
        bird = self.cmd("pgrep bird")
        if bird[0] == "":
            self.logger.warning("bird not running")
            return False
        #Getting config
        self.logger.debug("Reading bird config")
        configRaw = self.cmd("cat /etc/bird/bird.conf")[0].rstrip()
        #Parsing
        config = self.parse(configRaw)
        configs = self.cmd('ip addr show')
        #fping
        self.logger.debug("Running fping")
        result = self.getLatency(config,5)
        #update
        local = re.findall("inet (10\.0[0-9.]+\.1)\/(32|30) scope global lo",configs[0], re.MULTILINE | re.DOTALL)
        if not local: return False
        configRaw = re.sub(local[0][0]+"; #updated [0-9]+", local[0][0]+"; #updated "+str(int(time.time())), configRaw, 0, re.MULTILINE)
        for entry in result:
            if "latency" not in entry: continue
            configRaw = re.sub("cost "+str(entry['weight'])+"; #"+entry['target'], "cost "+str(entry['latency'])+"; #"+entry['target'], configRaw, 0, re.MULTILINE)
        if not result:
            self.logger.warning("Nothing todo")
        else:
            #reload bird with updates only every 5 minutes or if reload is greater than 1
            if (datetime.now().minute % 5 == 0 and runs == 0) or self.reload > 0:
                #write
                self.logger.info("Writing config")
                self.cmd("echo '"+configRaw+"' > /etc/bird/bird.conf")
                #reload
                self.logger.info("Reloading bird")
                self.cmd('sudo systemctl reload bird')
            else:
                self.logger.debug(f"{datetime.now().minute} not in window.")
        #however save any packetloss or jitter detected
        self.saveJson(self.network,f"{self.path}/configs/network.json")
        time.sleep(5)
        return self.noWait