import subprocess, requests, time

class Base:
    
    def cmd(self,command):
        p = subprocess.run(f"{command}", stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        return p.stdout.decode('utf-8')

    def call(self,url,payload):
        for run in range(1,5):
            try:
                req = requests.post(url, json=payload, timeout=(5,5))
                if req.status_code == 200: return req
                print(f"Got {req.text} as response")
            except Exception as ex:
                print(f"Error {ex}")
            print(f"Run {run} of 4")
            if run == 4:
                print("Aborting, limit reached.")
                return False
            time.sleep(2)

    def parse(self,configRaw):
        parsed = re.findall('interface "([a-zA-Z0-9]{3,}?)".{50,170}?cost ([0-9.]+);\s#([0-9.]+)',configRaw, re.DOTALL)
        data = []
        for nic,weight,target in parsed:
            data.append({'nic':nic,'target':target,'weight':weight})
        return data