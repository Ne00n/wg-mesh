import subprocess, requests, netaddr, time, json, re, os
from ipaddress import ip_network

class Base:
    
    def cmd(self,cmd,timeout=None):
        try:
            p = subprocess.run(cmd, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, timeout=timeout)
            return [p.stdout.decode('utf-8'),p.stderr.decode('utf-8')]
        except:
            return ["",""]

    def sameNetwork(self,origin,target):
        o = ip_network(origin, strict = False).network_address
        t = ip_network(target, strict = False).network_address
        return o == t

    def getRemote(self,local,subnetPrefixSplitted):
        parsed = re.findall(f'(({subnetPrefixSplitted[0]}\.{subnetPrefixSplitted[1]}\.[0-9]+\.)([0-9]+)\/31)',local, re.MULTILINE)[0]
        lastOctet = int(parsed[2])
        return parsed,f"{parsed[1]}{lastOctet-1}" if self.sameNetwork(f"{parsed[1]}{lastOctet-1}",parsed[0]) else f"{parsed[1]}{lastOctet+1}"

    def readConfig(self,file):
        if os.path.isfile(file):
            try:
                with open(file) as handle: return json.loads(handle.read())
            except Exception as e:
                return {}
        else:
            return {}

    def readFile(self,file):
        if os.path.isfile(file):
            try:
                with open(file, 'r') as file: return file.read()
            except Exception as e:
                return ""
        else:
            return ""

    def saveFile(self,data,path):
        try:
            with open(path, 'w') as file: file.write(data)
        except Exception as e:
            return False
        return True

    def saveJson(self,data,path):
        try:
            with open(path, 'w') as f: json.dump(data, f, indent=4)
        except Exception as e:
            return False
        return True

    def getRoutes(self,subnetPrefixSplitted=[10,0]):
        routes = self.cmd("birdc show route")[0]
        return re.findall(f"({subnetPrefixSplitted[0]}\.{subnetPrefixSplitted[1]}\.[0-9]+\.0\/30)",routes, re.MULTILINE)

    def getBirdLinks(self,configs,prefix="pipe",subnetPrefixSplitted=[10,0]):
        return re.findall(f"({prefix}[A-Za-z0-9]+): <POINTOPOINT.*?inet ({subnetPrefixSplitted[0]}[0-9.]+\.[0-9]+)",configs, re.MULTILINE | re.DOTALL)

    def resolve(self,ip,range,netmask):
        rangeDecimal = int(netaddr.IPAddress(range))
        ipDecimal = int(netaddr.IPAddress(ip))
        wildcardDecimal = pow( 2, ( 32 - int(netmask) ) ) - 1
        netmaskDecimal = ~ wildcardDecimal
        return ( ( ipDecimal & netmaskDecimal ) == ( rangeDecimal & netmaskDecimal ) )

    def filter(self,entry):
        ignoreNetworks = ["Ping"]
        if any(network in entry for network in ignoreNetworks): return False
        return True

    def getAvrg(self,row,weight=True):
        result,actual = 0,0
        if not row: return 65535
        for entry in row:
            #ignore timed out
            if entry[0] == "timed out": continue
            result += float(entry[0])
            actual += 1
        #do not return 0, never, ever
        if result == 0: return 65535
        #make sure its not below one
        if result < 1: result = 1
        if weight: return int(float(result / actual))
        else: return int(float(result / actual) * 10)

    def fping(self,targets,pings=3,dropTimeout = False):
        fping = f"fping -c {pings} "
        fping += " ".join(targets)
        result = self.cmd(fping)[0]
        parsed = re.findall("([0-9.:a-z]+).*?([0-9]+.[0-9]+|timed out).*?([0-9]+)% loss",result, re.MULTILINE)
        if not parsed: return {}
        latency =  {}
        for ip,ms,loss in parsed:
            if ip not in latency: latency[ip] = []
            if dropTimeout and ms == "timed out": continue
            latency[ip].append([ms,loss])
        return latency

    def call(self,url,payload,method="POST",max=5):
        allowedCodes = [200,412]
        for run in range(1,max):
            try:
                if method == "POST":
                    req = requests.post(url, json=payload, timeout=(5,5))
                else:
                    req = requests.patch(url, json=payload, timeout=(5,5))
                if req.status_code in allowedCodes: return req
                print(f"Got {req.text} as response")
            except Exception as ex:
                print(f"Error {ex}")
            print(f"Run {run} of 4")
            if run == 4:
                print("Aborting, limit reached.")
                return False
            time.sleep(2)

    def formatTable(self,list):
        longest,response = {},""
        for row in list:
            elements = row.split("\t")
            for index, entry in enumerate(elements):
                if not index in longest: longest[index] = 0
                if len(entry) > longest[index]: longest[index] = len(entry)
        for i, row in enumerate(list):
            elements = row.split("\t")
            for index, entry in enumerate(elements):
                if len(entry) < longest[index]:
                    diff = longest[index] - len(entry)
                    while len(entry) < longest[index]:
                        entry += " "
                response += f"{entry}" if response.endswith("\n") or response == "" else f" {entry}"
            if i < len(list) -1: response += "\n"
        return response

    def notify(self,server,title,message,priority=5):
        payload = {'title':title, 'message':message, 'priority':priority}
        req = self.call(server,payload,"POST")
        if req: return True