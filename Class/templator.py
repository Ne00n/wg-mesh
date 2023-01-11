class Templator:

    def genServer(self,interface,destination,serverID,serverIP,serverPort,ClientPublicKey):
        template = f'''#!/bin/bash
if [ "$1" == "up" ];  then
    sudo ip link add dev {interface} type wireguard
    sudo ip address add dev {interface} 10.0.{serverID}.{serverIP}/31
    #client {destination}
    sudo wg set {interface} listen-port {serverPort} private-key /opt/wg-mesh/links/{interface}.key peer {ClientPublicKey} allowed-ips 0.0.0.0/0
    sudo ip link set up dev {interface}
else
    sudo ip link delete dev {interface}
fi'''
        return template

    def genClient(self,interface,serverID,serverIP,serverIPExternal,serverPort,serverPublicKey):
        template = f'''#!/bin/bash
if [ "$1" == "up" ];  then
    sudo ip link add dev {interface} type wireguard
    sudo ip address add dev {interface} 10.0.{serverID}.{int(serverIP)+1}/31
    sudo wg set {interface} private-key /opt/wg-mesh/links/{interface}.key peer {serverPublicKey} allowed-ips 0.0.0.0/0 endpoint {serverIPExternal}:{serverPort}
    sudo ip link set up dev {interface}
else
    sudo ip link delete dev {interface}
fi'''
        return template

    def genVXLAN(self,targets):
        template = ""
        for node in targets: template += f'bridge fdb append 00:00:00:00:00:00 dev vxlan251 dst 10.0.{node}.1;'
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
    if net ~ [ 10.0.252.0/24+ ] then reject; #Source based Routing for Clients
    if net ~ [ 172.16.0.0/24+ ] then reject; #Wireguard VPN
    if net ~ [ 127.0.0.0/8+ ] then reject; #loopback
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
