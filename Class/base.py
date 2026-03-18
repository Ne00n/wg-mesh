import subprocess, requests, netaddr, shutil, time, json, re, os
from ipaddress import ip_network
from decimal import Decimal

class Base:

    def __init__(self):
        self.fpingMatch = re.compile(r"([0-9\.:a-z]+).*?([0-9]+.[0-9]+|timed out).*?([0-9]+)% loss")
        self.fpingUnreachable = re.compile(r"ICMP Host Unreachable from [0-9.]+ for ICMP Echo sent to ([0-9.]+)")
    
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

    def getRemote(self,config,subnetPrefixSplitted):
        parsed = re.findall(f'(({subnetPrefixSplitted[0]}\.{subnetPrefixSplitted[1]}\.[0-9]+\.)([0-9]+)\/31)',config, re.MULTILINE)[0]
        lastOctet = int(parsed[2])
        return parsed,f"{parsed[1]}{lastOctet-1}" if self.sameNetwork(f"{parsed[1]}{lastOctet-1}",parsed[0]) else f"{parsed[1]}{lastOctet+1}"

    def readJson(self,file):
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
        #Prevent file corruption
        total, used, free = shutil.disk_usage("/")
        usagePercent = (used / total) * 100
        if usagePercent >= 98: return False
        try:
            with open(path, 'w') as file: file.write(data)
        except Exception as e:
            return False
        return True

    def saveJson(self,data,path):
        #Prevent file corruption
        total, used, free = shutil.disk_usage("/")
        usagePercent = (used / total) * 100
        if usagePercent >= 98: return False
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
        ignoreNetworks = ["Ping","tunnel"]
        if any(network in entry for network in ignoreNetworks): return False
        return True

    def getAvrg(self,row):
        result,actual = 0,0
        if not row: return 65534
        for entry in row:
            result += Decimal(entry[0])
            actual += 1
        #do not return 0, never, ever
        if result == 0: return 65534
        #make sure its not below one
        if result < 1: result = 1
        result =  Decimal(result / actual)
        return result

    def fping(self,targets,pings=3):
        fping = f"fping -c {pings} "
        fping += " ".join(targets)
        result = self.cmd(fping)
        parsed, unreachable = [], []
        for row in result[0].splitlines(): parsed.append(re.findall(self.fpingMatch,row))
        for row in result[1].splitlines(): unreachable.append(re.findall(self.fpingUnreachable,row))
        if not parsed: return {}
        latency =  {}
        for row in parsed:
            for ip,ms,loss in row:
                if ip not in latency: latency[ip] = []
                if ms == "timed out": continue
                latency[ip].append([ms,loss])
        for row in unreachable:
            for ip in row:
                if ip not in latency: latency[ip] = []
        return latency

    def iperf(self,target):
        iperf = f"iperf3 -c {target}"
        result = self.cmd(iperf)[0]
        parsed = re.findall("([0-9]+) Mbits\/sec.*?sender",result, re.MULTILINE)
        if not parsed: return 0
        return parsed[0]

    def call(self,url,payload,method="POST",headers={},max=5):
        allowedCodes, crashed = [200,412,451], False
        for run in range(1,max):
            try:
                if method == "POST":
                    req = requests.post(url, json=payload, timeout=(5,5))
                elif method == "GET":
                    req = requests.get(url, headers=headers, timeout=(5,5))
                else:
                    req = requests.patch(url, json=payload, timeout=(5,5))
                if req.status_code in allowedCodes: return True,req
                crashed = False
            except Exception as ex:
                crashed = True
                pass
            if run == 4 and not crashed:
                return False,req
            elif run == 4:
                return False,None
            time.sleep(2)

    def notify(self,server,title,message,priority=5):
        payload = {'title':title, 'message':message, 'priority':priority}
        success, req = self.call(server,payload,"POST")
        if success: return True

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