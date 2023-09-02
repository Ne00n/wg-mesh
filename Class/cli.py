from Class.wireguard import Wireguard
from Class.templator import Templator
from Class.base import Base
import subprocess, sys, os

class CLI(Base):

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
        subprocess.run("cd; git pull",shell=True)

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

    def disable(self,option):
        if "mesh" in option:
            self.wg.saveJson({},f"{self.path}/configs/state.json")
        elif "ospfv3" in option:
            config = self.readConfig(f"{self.path}/configs/config.json")
            config['ospfv3'] = False
            self.saveJson(config,f"{self.path}/configs/config.json")
        elif "wgobfs" in option:
            config = self.readConfig(f"{self.path}/configs/config.json")
            if "wgobfs" in config['linkTypes']: config['linkTypes'].remove("wgobfs")
            self.saveJson(config,f"{self.path}/configs/config.json")
        else:
            print("Valid options: mesh, ospfv3")
            
    def enable(self,option):
        if "mesh" in option:
            if os.path.isfile(f"{self.path}/configs/state.json"): os.remove(f"{self.path}/configs/state.json")
        elif "ospfv3" in option:
            config = self.readConfig(f"{self.path}/configs/config.json")
            config['ospfv3'] = True
            self.saveJson(config,f"{self.path}/configs/config.json")
        elif "wgobfs" in option:
            config = self.readConfig(f"{self.path}/configs/config.json")
            if not "wgobfs" in config['linkTypes']: config['linkTypes'].append("wgobfs")
            self.saveJson(config,f"{self.path}/configs/config.json")
            print("You still need to install wgobfs with: bash /opt/wg-mesh/tools/wgobfs.sh")
        else:
            print("Valid options: mesh, ospfv3")

    def setOption(self,options):
        validOptions = ["area","prefix","defaultLinkType"]
        key, value = options
        if key in validOptions:
            config = self.readConfig(f"{self.path}/configs/config.json")
            config[key] = value
            self.saveJson(config,f"{self.path}/configs/config.json")
        else:
            print(f"Valid options: {', '.join(validOptions)}")
        