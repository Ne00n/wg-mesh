import subprocess, requests, time

class Base:
    
    def cmd(self,command):
        p = subprocess.run(f"{command}", stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        return p.stdout.decode('utf-8')

    def call(self,url,payload):
        for run in range(4):
            print(f"Retrying {run+1} of 4")
            try:
                req = requests.post(url, json=payload)
                if req.status_code == 200: return req
                print(f"Got {req.text} as response")
            except Exception as ex:
                print(f"Error {ex}")
            if run == 3:
                print("Aborting, limit reached.")
                return False
            time.sleep(2)