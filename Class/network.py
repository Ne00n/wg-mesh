class Network:

    def __init__(self,path):
        self.config = config
        self.subnetPrefix = ".".join(self.config['subnet'].split(".")[:2])

    def getNodeSubnet(self):
        if self.config['subnet'].startswith("10."):
            return f"{self.subnetPrefix}.{self.config['id']}.0/23"
        else:
            return f"{self.subnetPrefix}.{self.config['id']}.0/24"

    def getNodeSubnetv6(self):
        return f"fe82:{self.config['id']}::/32"