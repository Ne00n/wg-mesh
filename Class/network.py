import ipaddress

class Network:

    def __init__(self,config):
        self.config = config
        self.subnetPrefix = ".".join(self.config['subnet'].split(".")[:2])

    def getNodeSubnet(self):
        if self.config['subnet'].startswith("10."):
            return f"{self.subnetPrefix}.{self.config['id']}.0/23"
        else:
            return f"{self.subnetPrefix}.{self.config['id']}.0/24"

    def getNodeSubnetv6(self):
        return f"fe82:{self.config['id']}::/112"

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