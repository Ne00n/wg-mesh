from logging.handlers import RotatingFileHandler
from Class.wireguard import Wireguard
from Class.templator import Templator
from Class.base import Base
from Class.bird import Bird
import subprocess, logging, sys, os

class CLI(Base):

    def __init__(self,path):
        self.path = path
        self.templator = Templator()
        self.wg = Wireguard(path,True)

    def init(self,id,listen):
        self.wg.init(id,listen)

    def used(self):
        self.wg = Wireguard(self.path)
        self.wg.used()

    def bender(self):
        self.wg = Wireguard(self.path)
        self.wg.bender()

    def connect(self,dest,token,linkType="default",port=51820,network=""):
        self.wg = Wireguard(self.path)
        self.wg.connect(dest,token,linkType,port,network)

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
        self.wg = Wireguard(self.path,False,True)
        self.wg.updateConfig()

    def recover(self):
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.DEBUG)
        logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',datefmt='%d.%m.%Y %H:%M:%S',level=logging.DEBUG,handlers=[RotatingFileHandler(maxBytes=10000000,backupCount=5,filename=f"{self.path}/logs/recovery.log"),stream_handler])
        logger = logging.getLogger()
        self.bird = Bird(self.path,logger)
        self.bird.bird(True)

    def token(self):
        tokens = self.readConfig(f"{self.path}/tokens.json")
        if tokens:
            print(f"Connect: {','.join(tokens['connect'])}")
        else:
            print("Unable to load the tokens.json")

    def status(self):
        print("--- Services ----")
        proc = self.cmd("systemctl status bird")[0]
        birdRunning = "Bird2 is not running." if not "running" in proc else "Bird2 is running."
        proc = self.cmd("systemctl status wgmesh")[0]
        wgmeshRunning = "wgmesh is not running." if not "running" in proc else "wgmesh is running."
        proc = self.cmd("systemctl status wgmesh-bird")[0]
        wgmeshBirdRunning = "wgmesh-bird is not running." if not "running" in proc else "wgmesh-bird is running."
        print(f"{birdRunning}\t{wgmeshRunning}\t{wgmeshBirdRunning}")
        print("--- Wireguard ---")
        network = self.readConfig(f"{self.path}/configs/network.json")
        print("Destination\tPacketloss\tJitter")
        jittar,loss = 0,0
        for dest,data in network.items():
            hasLoss,hasJitter = "No","No"
            if dest == "updated": continue
            if data['packetloss']:
                hasLoss = "Yes"
                loss += 1
            if data['jitter']:
                hasJitter = "Yes"
                jittar += 1
            print(f"{dest}\t{hasLoss}\t\t{hasJitter}")
        print(f"{len(network) -1}\t\t{loss}\t\t{jittar}")


    def disable(self,option):
        config = self.readConfig(f"{self.path}/configs/config.json")
        if "mesh" in option:
            self.wg.saveJson({},f"{self.path}/configs/state.json")
        elif "ospfv2" in option:
            config['bird']['ospfv2'] = False
        elif "ospfv3" in option:
            config['bird']['ospfv3'] = False
        elif "client" in option:
            config['bird']['client'] = False
        elif "wgobfs" in option:
            if "wgobfs" in config['linkTypes']: config['linkTypes'].remove("wgobfs")
        elif "ipt_xor" in option:
            if "ipt_xor" in config['linkTypes']: config['linkTypes'].remove("ipt_xor")
        else:
            print("Valid options: mesh, ospfv2, ospfv3, wgobfs, ipt_xor, client")
            return
        self.saveJson(config,f"{self.path}/configs/config.json")
        print("You should reload the services to apply any config changes")
            
    def enable(self,option):
        config = self.readConfig(f"{self.path}/configs/config.json")
        if "mesh" in option:
            if os.path.isfile(f"{self.path}/configs/state.json"): os.remove(f"{self.path}/configs/state.json")
        elif "ospfv2" in option:
            config['bird']['ospfv2'] = True
        elif "ospfv3" in option:
            config['bird']['ospfv3'] = True
        elif "client" in option:
            config['bird']['client'] = True
        elif "wgobfs" in option:
            if not "wgobfs" in config['linkTypes']: config['linkTypes'].append("wgobfs")
            print("You still need to install wgobfs with: bash /opt/wg-mesh/tools/wgobfs.sh")
        elif "ipt_xor" in option:
            if not "ipt_xor" in config['linkTypes']: config['linkTypes'].append("ipt_xor")
            print("You still need to install ipt_xor with: bash /opt/wg-mesh/tools/xor.sh")
        else:
            print("Valid options: mesh, ospfv2, ospfv3, wgobfs, ipt_xor, client")
            return
        self.saveJson(config,f"{self.path}/configs/config.json")
        print("You should reload the services to apply any config changes")

    def setOption(self,options):
        validOptions = ["area","prefix","defaultLinkType","basePort","tick","subnet","vxlan","AllowedPeers"]
        if len(sys.argv) == 0:
            print(f"Valid options: {', '.join(validOptions)}")
        else:
            key, value = options
            if key in validOptions:
                config = self.readConfig(f"{self.path}/configs/config.json")
                if key == "basePort" or key == "vxlan":
                    config[key] = int(value)
                elif key == "area" or key == "tick":
                    config['bird'][key] = int(value)
                elif key == "AllowedPeers":
                    if value in config['AllowedPeers']:
                        config['AllowedPeers'].remove(value)
                    else:
                        config['AllowedPeers'].append(value)
                else:
                    config[key] = value
                self.saveJson(config,f"{self.path}/configs/config.json")
                print("You should reload the services to apply any config changes")
                if key == "subnet" or key == "vxlan":        
                    print("Reconfiguring dummy")
                    self.wg = Wireguard(self.path)
                    self.wg.reconfigureDummy()
            else:
                print(f"Valid options: {', '.join(validOptions)}")
        