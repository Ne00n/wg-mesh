import subprocess, requests, json, time, sys, re, os
from datetime import datetime
from Class.base import Base
from random import randint

class Latency(Base):
    def __init__(self,path):
        self.path = path
        file = f"{path}/configs/network.json"
        if os.path.isfile(file):
            print("Loading","network.json")
            try:
                with open(file) as handle:
                    self.network = json.loads(handle.read())
            except:
                self.network = {"created":int(datetime.now().timestamp()),"updated":0}
        else:
            self.network = {"created":int(datetime.now().timestamp()),"updated":0}

    def save(self):
        print(f"Saving network.json")
        with open(f"{self.path}/configs/network.json", 'w') as f:
            json.dump(self.network, f, indent=4)

    def parse(self,configRaw):
        parsed = re.findall('interface "([a-zA-Z0-9]{3,}?)".{50,170}?cost ([0-9.]+);\s#([0-9.]+)',configRaw, re.DOTALL)
        data = []
        for nic,weight,target in parsed:
            data.append({'nic':nic,'target':target,'weight':weight})
        return data

    def getAvrg(self,row,weight=False):
        result = 0
        if not row: return 65000
        for entry in row:
            result += float(entry[0])
        if weight: return int(float(result / len(row)))
        else: return int(float(result / len(row)) * 10)

    def hasJitter(self,row,avrg):
        grace = 20
        for entry in row:
            if float(entry[0]) > avrg + grace: return True,float(entry[0]) - (avrg + grace)
        return False,0

    def getLatency(self,config,pings=4):
        fping = ["fping", "-c", str(pings)]
        for row in config:
            fping.append(row['target'])
        result = subprocess.run(fping, stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        parsed = re.findall("([0-9.]+).*?([0-9]+.[0-9]).*?([0-9])% loss",result.stdout.decode('utf-8'), re.MULTILINE)
        latency =  {}
        for ip,ms,loss in parsed:
            if ip not in latency: latency[ip] = []
            latency[ip].append([ms,loss])
        for entry,row in latency.items():
            del row[0] #drop the first ping result
            row.sort()
            #del row[len(row) -1] #drop the highest ping result
        current = int(datetime.now().timestamp())
        self.total,self.hadLoss,self.hasLoss,self.hadJitter = 0,0,0,0
        for node in list(config):
            for entry,row in latency.items():
                if entry == node['target']:
                    node['latency'] = self.getAvrg(row)
                    if entry not in self.network: self.network[entry] = {"packetloss":{},"jitter":{}}

                    #Packetloss
                    hasLoss,peakLoss = len(row) < pings -1,(pings -1) - len(row)
                    if hasLoss:
                        #keep for 15 minutes / 3 runs
                        self.network[entry]['packetloss'][int(datetime.now().timestamp()) + 900] = peakLoss
                        print(entry,"Packetloss detected","got",len(row),f"of {pings -1}")
                        self.hasLoss =+ 1

                    threshold,eventCount,eventScore = 1,0,0
                    for event,lost in list(self.network[entry]['packetloss'].items()):
                        if int(event) > int(datetime.now().timestamp()): 
                            eventCount += 1
                            eventScore += lost
                        #delete events after 60 minutes
                        elif (int(datetime.now().timestamp()) - 3600) > int(event):
                            del self.network[entry]['packetloss'][event]
                    
                    if eventCount > 0: eventScore = eventScore / eventCount
                    hadLoss = True if eventCount >= threshold else False
                    if hadLoss:
                        tmpLatency = node['latency']
                        node['latency'] = node['latency'] + (50 * eventScore) #+ 50ms / weight
                        print(entry,"Ongoing Packetloss",tmpLatency,node['latency'],eventScore)
                        self.hadLoss += 1

                    #Jitter
                    hasJitter,peakJitter = self.hasJitter(row,self.getAvrg(row,True))
                    if hasJitter:
                        #keep for 15 minutes / 3 runs
                        self.network[entry]['jitter'][int(datetime.now().timestamp()) + 900] = peakJitter
                        print(entry,"High Jitter dectected")

                    threshold,eventCount,eventScore = 2,0,0
                    for event,peak in list(self.network[entry]['jitter'].items()):
                        if int(event) > int(datetime.now().timestamp()): 
                            eventCount += 1
                            eventScore += peak
                        #delete events after 60 minutes
                        elif (int(datetime.now().timestamp()) - 3600) > int(event):
                            del self.network[entry]['jitter'][event]
                    
                    if eventCount > 0: eventScore = eventScore / eventCount
                    hadJitter = True if eventCount > threshold else False
                    if hadJitter:
                        node['latency'] = node['latency'] + (eventScore * 10) #+ packetloss /weight
                        print(entry,"Ongoing Jitter")
                        self.hadJitter += 1

                    self.total += 1
                    #make sure its always int
                    node['latency'] = int(node['latency'])

        print (f"Total {self.total}, Jitter {self.hadJitter}, Packetloss {self.hadLoss}")
        self.network['updated'] = int(datetime.now().timestamp())
        return config

    def run(self):
        #Check if bird is running
        print("Checking bird status")
        bird = self.cmd("pgrep bird")
        if bird[0] == "":
            print("bird not running")
            return False
        #Getting config
        print("Reading bird config")
        configRaw = self.cmd("cat /etc/bird/bird.conf")[0].rstrip()
        #Parsing
        config = self.parse(configRaw)
        configs = self.cmd('ip addr show')
        #fping
        print("Running fping")
        result = self.getLatency(config,11)
        #update
        local = re.findall("inet (10\.0[0-9.]+\.1)\/(32|30) scope global lo",configs[0], re.MULTILINE | re.DOTALL)
        if not local: return False
        configRaw = re.sub(local[0][0]+"; #updated [0-9]+", local[0][0]+"; #updated "+str(int(time.time())), configRaw, 0, re.MULTILINE)
        for entry in result:
            if "latency" not in entry: continue
            configRaw = re.sub("cost "+str(entry['weight'])+"; #"+entry['target'], "cost "+str(entry['latency'])+"; #"+entry['target'], configRaw, 0, re.MULTILINE)
        if not result:
            print("Nothing to do")
        else:
            #reload bird with updates only every 5 minutes or if packetloss is detected
            if datetime.now().minute % 5 == 0 or self.hasLoss > 0:
                #write
                print("Writing config")
                self.cmd("echo '"+configRaw+"' > /etc/bird/bird.conf")
                #reload
                print("Reloading bird")
                self.cmd('sudo systemctl reload bird')
            else:
                print(f"{datetime.now().minute} not in window.")
        #however save any packetloss or jitter detected
        self.save()