import subprocess, requests, netaddr, time, re
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

    def resolve(self,ip,range,netmask):
        rangeDecimal = int(netaddr.IPAddress(range))
        ipDecimal = int(netaddr.IPAddress(ip))
        wildcardDecimal = pow( 2, ( 32 - int(netmask) ) ) - 1
        netmaskDecimal = ~ wildcardDecimal
        return ( ( ipDecimal & netmaskDecimal ) == ( rangeDecimal & netmaskDecimal ) )

    def filter(self,entry):
        if "Ping" in entry: return False
        return True

    def getAvrg(self,row,weight=True):
        result = 0
        if not row: return 65000
        for entry in row:
            #ignore timed out
            if entry[0] == "timed out": continue
            result += float(entry[0])
        #do not return 0, never, ever
        if result == 0: return 65000
        if weight: return int(float(result / len(row)))
        else: return int(float(result / len(row)) * 10)

    def fping(self,targets,pings=3,dropTimeout = False):
        fping = f"fping -c {pings} "
        fping += " ".join(targets)
        result = self.cmd(fping)[0]
        parsed = re.findall("([0-9.:a-z]+).*?([0-9]+.[0-9]+|timed out).*?([0-9]+)% loss",result, re.MULTILINE)
        if not parsed: return False
        latency =  {}
        for ip,ms,loss in parsed:
            if ip not in latency: latency[ip] = []
            if dropTimeout and ms == "timed out": continue
            latency[ip].append([ms,loss])
        return latency

    def call(self,url,payload,method="POST",max=5):
        for run in range(1,max):
            try:
                if method == "POST":
                    req = requests.post(url, json=payload, timeout=(5,5))
                else:
                    req = requests.patch(url, json=payload, timeout=(5,5))
                if req.status_code == 200: return req
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