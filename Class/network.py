from Class.base import Base
import ipaddress

class Network(Base):

    def __init__(self,config):
        self.config = config
        self.prefix = self.config['prefix']
        self.subnetPrefix = self.getSubnetOctet(splitBy=2)

    def getSubnetOctet(self,splitBy=0,isPeer=False):
        selector = 'subnetPeer' if isPeer else 'subnet'
        if splitBy == 0:
            return ".".join(self.config[selector].split("."))
        else:
            return ".".join(self.config[selector].split(".")[:splitBy])

    def getRoutes(self,subnetPrefixSplitted=self.getSubnetOctet()):
        routes = self.cmd("birdc show route")[0]
        return re.findall(f"({subnetPrefixSplitted[0]}\.{subnetPrefixSplitted[1]}\.[0-9]+\.0\/30)",routes, re.MULTILINE)

    def getBirdLinks(self,configs,subnetPrefixSplitted=self.getSubnetOctet()):
        return re.findall(f"({self.prefix}[A-Za-z0-9]+): <POINTOPOINT.*?inet ({subnetPrefixSplitted[0]}[0-9.]+\.[0-9]+)",configs, re.MULTILINE | re.DOTALL)

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