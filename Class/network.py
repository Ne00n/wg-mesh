from Class.base import Base
import ipaddress, re

class Network(Base):

    def __init__(self,config):
        super().__init__()
        self.config = config
        self.prefix = self.config['prefix']
        self.subnetSplitted = self.getSubnetOctet()
        self.subnetPrefix = ".".join(self.subnetSplitted[:2])
        self.subnetPeerSplitted = self.getSubnetOctet(isPeer=True)
        self.subnetPeerPrefix = ".".join(self.subnetPeerSplitted[:2])

    def getSubnetOctet(self,isPeer=False):
        selector = 'subnetPeer' if isPeer else 'subnet'
        return self.config[selector].split(".")

    def subnetSwitch(self,network=""):
        if "peer" in network or "tunnel" in network:
            return self.subnetPeerSplitted,self.subnetPeerPrefix
        else:
            return self.subnetSplitted,self.subnetPrefix

    def getRoutes(self,subnetSplitted=None):
        if subnetSplitted is None: subnetSplitted = self.subnetSplitted
        routes = self.cmd("birdc show route")[0]
        return re.findall(f"({subnetSplitted[0]}\.{subnetSplitted[1]}\.[0-9]+\.0\/30)",routes, re.MULTILINE)

    def getBirdLinks(self,subnetSplitted=None):
        if subnetSplitted is None: subnetSplitted = self.subnetSplitted
        configs = self.cmd('ip addr show')[0]
        return re.findall(f"({self.prefix}[A-Za-z0-9]+): <POINTOPOINT.*?inet ({subnetSplitted[0]}[0-9.]+\.[0-9]+)",configs, re.MULTILINE | re.DOTALL)

    def getNodeSubnet(self,isPeer=False):
        if isPeer:
            return f"{self.subnetPeerPrefix}.{self.config['id']}.0/24"
        elif self.config['subnet'].startswith("10."):
            return f"{self.subnetPrefix}.{self.config['id']}.0/23"
        else:
            return f"{self.subnetPrefix}.{self.config['id']}.0/24"

    def getNodeSubnetv6(self,isPeer=False):
        if isPeer:
            return f"{self.config['subnetPeerv6']}{self.config['id']}::/112"
        else:
            return f"{self.config['subnetv6']}{self.config['id']}::/112"

    def getPeerSubnets(self,isPeer=False):
        nodeSubnet = self.getNodeSubnet(isPeer)
        network = ipaddress.ip_network(nodeSubnet)
        subnets = list(network.subnets(new_prefix=31))
        subnets = subnets[2:]
        return subnets

    def getPeerSubnetsv6(self,isPeer=False):
        nodeSubnet = self.getNodeSubnetv6(isPeer)
        network = ipaddress.ip_network(nodeSubnet)
        return list(network.subnets(new_prefix=127))

    def getHost(self,freeSubnet,suffix="31"):
        peerSubnet = ipaddress.ip_network(freeSubnet)
        return f"{list(peerSubnet.hosts())[1]}/{suffix}"

    def filterLocalIP(self,targets,localIP):
        for ip in list(targets):
            if self.resolve(localIP,ip.replace("/30",""),30):
                targets.remove(ip)
                return targets

    def filterExisting(self,targets,links):
        for ip in list(targets):
            for link in links:
                if self.resolve(link[1],ip.replace("/30",""),24):
                    #multiple links in the same subnet
                    if ip in targets: targets.remove(ip)
        return targets

    def filterLocalLinks(self,targets,links):
        for ip in list(targets):
            for link in links:
                splitted = ip.split(".")
                if f"pipe{splitted[2]}" == link[0]:
                    #multiple links in the same subnet
                    if ip in targets: targets.remove(ip)
        return targets

    def filterIDs(self,targets,dropHigher=False):
        for ip in list(targets):
            splitted = ip.split(".")
            if int(splitted[2]) >= 200: 
                targets.remove(ip)
                continue
            if dropHigher and int(splitted[2]) > self.config['id']:
                targets.remove(ip)
        return targets

    def getSubnetSplitted(self):
        return self.subnetSplitted

    def getSubnetPrefix(self):
        return self.subnetPrefix