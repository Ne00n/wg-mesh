import re

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