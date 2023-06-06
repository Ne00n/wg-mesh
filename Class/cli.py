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

    def connect(self,dest,token):
        self.wg = Wireguard(self.path)
        self.wg.connect(dest,token)

    def optimize(self):
        self.wg = Wireguard(self.path)
        self.wg.optimize()

    def disconnect(self,force=False,link=""):
        self.wg = Wireguard(self.path)
        self.wg.disconnect(force,link)

    def links(self,state):
        files = os.listdir(f'{self.path}/links/')
        for file in list(files):
            if not file.endswith(".sh"): files.remove(file)
        for file in files:
            subprocess.run(f"bash {self.path}/links/{file} {state}",shell=True)