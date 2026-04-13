import ipaddress, re

class Validate():

    def id(self,id):
        result = re.findall(r"^[0-9]{1,4}$",str(id),re.MULTILINE | re.DOTALL)
        if not result: return False
        return True

    def port(self,port):
        result = re.findall(r"^[0-9]{4,5}$",str(port),re.MULTILINE | re.DOTALL)
        if not result: return False
        return True

    def network(self,network):
        result = re.findall(r"^[A-Za-z]{3,6}$",network,re.MULTILINE | re.DOTALL)
        if not result: return False
        return True

    def linkType(self,linkType,config):
        linkTypes = ["default","wgobfs","ipt_xor","amneziawg"]
        if not linkType in linkTypes: return False
        if not linkType in config['linkTypes']: return False
        return True

    def prefix(self,prefix):
        result = re.findall(r"^[0-9.]{4,6}$",prefix,re.MULTILINE | re.DOTALL)
        if not result: return False
        return True

    def token(self,payload,tokens):
        if not "token" in payload: return False
        token = re.findall(r"^([A-Za-z0-9/.=+]{18,60})$",payload['token'],re.MULTILINE | re.DOTALL)
        if not token: return False
        if "network" in payload and payload["network"] == "peer":
            if payload['token'] not in tokens['peer']: return False
        else:
            if payload['token'] not in tokens['connect']: return False
        return True

    def protocol(self,protocol):
        allowedProtocols = ["ipv4","ipv6"]
        if not protocol in allowedProtocols: return False
        return True

    def validateConnectivity(connectivity):
        if "ipv4" not in connectivity or "ipv6" not in connectivity: return False
        try:
            if connectivity['ipv4']:
                ip_obj = ipaddress.ip_address(connectivity['ipv4'])
            if connectivity['ipv6']:
                ip_obj = ipaddress.ip_address(connectivity['ipv6'])
        except ValueError:
            return False
        return True

    def connect(self,payload,config):
        #validate id
        if not 'id' in payload or not self.id(payload['id']): 
            return 400,"Invalid ID"
        #validate port
        if "port" in payload and not self.port(payload['port']): 
            return 400,"Invalid Port"
        #validate prefix
        if "prefix" in payload and not self.prefix(payload['prefix']): 
            return 400,"Invalid Prefix"
        #validate network
        if "network" in payload and payload['network'] != "" and not self.network(payload['network']):
            return 400,"Invalid Network"
        #validate linkType
        if "linkType" in payload and not self.linkType(payload['linkType'],config):
            return 400,"Invalid linkType"
        #validate connectivity
        if "connectivity" in payload and not self.validateConnectivity(payload['connectivity']):
            return 400,"Invalid connectivity data"
        #validate protocol
        if not "protocol" in payload and not self.protocol(payload['protocol']):
            return 400,"Invalid protocol"
        #prevent local connects
        if payload['id'] == config['id']:
            return 400,"Invalid Origin"
        return None,None