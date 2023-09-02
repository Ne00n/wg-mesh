from Class.wireguard import Wireguard
from Class.templator import Templator
import subprocess, sys, os

class CLI:

    def __init__(self,path):
        self.path = path
        self.templator = Templator()
        self.wg = Wireguard(path,True)

    def init(self,id,listen):
        self.wg.init(id,listen)

    def connect(self,dest,token,linkType="default"):
        self.wg = Wireguard(self.path)
        self.wg.connect(dest,token,linkType)

    def proximity(self,cutoff=0):
        self.wg = Wireguard(self.path)
        self.wg.proximity(cutoff)

    def disconnect(self,links=[],force=False):
        self.wg = Wireguard(self.path)
        self.wg.disconnect(links,force)

    def links(self,state):
        files = os.listdir(f'{self.path}/links/')
        for file in list(files):
            if not file.endswith(".sh"): files.remove(file)
        for file in files:
            subprocess.run(f"bash {self.path}/links/{file} {state}",shell=True)

    def update(self):
        subprocess.run("git pull",shell=True)

    def clean(self):
        self.wg = Wireguard(self.path)
        self.wg.clean()

    def migrate(self):
        self.wg = Wireguard(self.path)
        self.wg.updateConfig()

    def token(self):
        if os.path.isfile(f"{self.path}/token"):
            with open(f'{self.path}/token') as f:
                print(f.read().rstrip())
        else:
            print("Unable to load the token file")