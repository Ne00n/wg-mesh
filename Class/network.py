from Class.base import Base
import ipaddress, re

class Network(Base):

    def __init__(self,config):
        self.config = config
        self.prefix = self.config['prefix']
        self.subnetSplitted = self.getSubnetOctet()
        self.subnetPrefix = ".".join(self.subnetSplitted[:2])
        self.subnetPeerSplitted = self.getSubnetOctet(isPeer=True)
        self.subnetPeerPrefix = ".".join(self.subnetPeerSplitted[:2])

    def getSubnetOctet(self,isPeer=False):
        selector = 'subnetPeer' if isPeer else 'subnet'
        return self.config[selector].split(".")

    def getSubnetSplitted(self):
        return self.subnetSplitted

    def getSubnetPeerSplitted(self):
        return self.subnetPeerSplitted

    def getSubnetPeerPrefix(self):
        return self.subnetPeerPrefix

    def getSubnetPrefix(self):
        return self.subnetPrefix

    def getRoutes(self,subnetSplitted=None):
        if subnetSplitted is None: subnetSplitted = self.subnetSplitted
        routes = self.cmd("birdc show route")[0]
        return re.findall(f"({subnetSplitted[0]}\.{subnetSplitted[1]}\.[0-9]+\.0\/30)",routes, re.MULTILINE)

    def getBirdLinks(self,subnetSplitted=None):
        if subnetSplitted is None: subnetSplitted = self.subnetSplitted
        configs = self.cmd('ip addr show')[0]
        return re.findall(f"({self.prefix}[A-Za-z0-9]+): <POINTOPOINT.*?inet ({subnetSplitted[0]}[0-9.]+\.[0-9]+)",configs, re.MULTILINE | re.DOTALL)

    def getNodeSubnet(self):
        if self.config['subnet'].startswith("10."):
            return f"{self.subnetPrefix}.{self.config['id']}.0/23"
        else:
            return f"{self.subnetPrefix}.{self.config['id']}.0/24"

    def getNodeSubnetv6(self):
        return f"{self.config['subnetLinkLocal']}{self.config['id']}::/112"

    def getPeerSubnets(self):
        nodeSubnet = self.getNodeSubnet()
        network = ipaddress.ip_network(nodeSubnet)
        subnets = list(network.subnets(new_prefix=31))
        subnets = subnets[2:]
        return subnets

    def getPeerSubnetsv6(self):
        nodeSubnet = self.getNodeSubnetv6()
        network = ipaddress.ip_network(nodeSubnet)
        return list(network.subnets(new_prefix=127))

    def getHost(self,freeSubnet,suffix="31"):
        peerSubnet = ipaddress.ip_network(freeSubnet)
        return f"{list(peerSubnet.hosts())[1]}/{suffix}"