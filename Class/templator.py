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
    
    def getFirst(self,latency):
        for entry in latency: return entry

    def genBird(self,latency,local,time):
        firstNode = self.getFirst(latency)
        if not local:
            routerID = latency[firstNode]["origin"]
        else:
            routerID = local[0][0]
        template = f'''log syslog all;
router id {routerID}; #updated '''+str(time)+'''

protocol device {
    scan time 10;
}
'''
        localPTP = ""
        for target,data in latency.items():
            if localPTP != "":
                localPTP += ","
            localPTP += data['target']+"/32-"
        template += '''
function avoid_local_ptp() {
### Avoid fucking around with direct peers
return net ~ [ '''+localPTP+''' ];
}

protocol direct {
    ipv4;
    interface "lo";
}

protocol kernel {
	ipv4 {
	    export filter { '''
        if local:
            template += 'krt_prefsrc = '+routerID+';'
        template += '''
        if avoid_local_ptp() then reject;
            accept;
        };
    };
}

protocol kernel {
    ipv6 { export all; };
}

filter export_OSPF {
    include "bgp_ospf.conf";
    if net ~ [ 10.0.252.0/24+ ] then reject; #Source based Routing for Clients
    if net ~ [ 172.16.0.0/24+ ] then reject; #Wireguard VPN
    if source ~ [ RTS_DEVICE, RTS_STATIC ] then accept;
    reject;
}

protocol ospf {
ipv4 {
        import all;
        export filter export_OSPF;
    };
	area 0 { '''
        for target,data in latency.items():
            template += '''
                interface "'''+target+'''" {
                        type ptmp;
                        neighbors {
                        '''+data['target']+''';
                        };
                        cost '''+str(data['latency'])+'''; #'''+data['target']+'''
                };
            '''
        template += """
        };
}"""
        return template
