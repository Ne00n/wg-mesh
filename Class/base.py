import subprocess, requests, time
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

    def getAvrg(self,list):
        result = 0
        for ms in list:
            result += float(ms)
        return round(float(result / len(list)),2)

    def fping(self,targets,pings=3):
        fping = f"fping -c {pings} "
        fping += ",".join(targets)
        result = self.cmd(fping)[0]
        parsed = re.findall("([0-9.]+).*?([0-9]+.[0-9]+|timed out).*?([0-9]+)% loss",result, re.MULTILINE)
        if not parsed: return False
        latency =  {}
        for ip,ms,loss in parsed:
            if ip not in latency: latency[ip] = []
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