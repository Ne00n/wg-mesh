import re

class Validate():

    def id(self,id):
        result = re.findall(r"^[0-9]{1,4}$",str(id),re.MULTILINE | re.DOTALL)
        if not result: return False
        return True