from Class.wireguard import Wireguard
from Class.templator import Templator
from Class.bird import Bird
import subprocess, sys, os

class CLI:

    def __init__(self,path):
        self.path = path
        self.templator = Templator()
        self.wg = Wireguard(path,True)
        self.bird = Bird(path)

    def init(self,name,id):
        self.wg.init(name,id)

    def connect(self,dest,token):
        self.wg = Wireguard(self.path)
        self.wg.connect(dest,token)

    def disconnect(self,force=False,link=""):
        self.wg = Wireguard(self.path)
        self.wg.disconnect(force,link)

    def links(self,state):
        files = os.listdir(f'{self.path}/links/')
        for file in list(files):
            if not file.endswith(".sh"): files.remove(file)
        for file in files:
            subprocess.run(f"bash {self.path}/links/{file} {state}",shell=True)