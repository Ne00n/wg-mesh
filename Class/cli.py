from Class.wireguard import Wireguard
from Class.templator import Templator
from Class.bird import Bird

class CLI:

    def __init__(self,path):
        self.path = path
        self.templator = Templator()
        self.wg = Wireguard(path,False)
        self.bird = Bird()

    def init(self,name,id):
        self.wg.init(name,id)

    def connect(self,dest,token):
        self.wg = Wireguard(self.path)
        self.wg.connect(dest,token)
        self.bird.bird()

    def disconnect(self):
        self.wg = Wireguard(self.path)
        self.wg.disconnect()
