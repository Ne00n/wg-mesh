class Templator:
    def genServer(self,serverID,serverIP,serverPort,serverPrivateKey,ClientPublicKey):
        template = f'''[Interface]
Address = 10.0.{serverID}.{serverIP}/31
ListenPort = {serverPort}
PrivateKey = {serverPrivateKey}
SaveConfig = true
Table = off
[Peer]
PublicKey = {ClientPublicKey}
AllowedIPs = 0.0.0.0/0'''
        return template
    def genClient(self,serverID,serverIP,serverIPExternal,serverPort,clientPrivateKey,serverPublicKey):
        template = f'''[Interface]
Address = 10.0.{serverID}.{int(serverIP)+1}/31
PrivateKey = {clientPrivateKey}
Table = off
[Peer]
PublicKey = {serverPublicKey}
AllowedIPs = 0.0.0.0/0
Endpoint = {serverIPExternal}:{serverPort}'''
        return template
