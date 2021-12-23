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

    def genVXLAN(self,targets):
        template = ""
        for node in targets: template += f'bridge fdb append 00:00:00:00:00:00 dev vxlan251 dst 10.0.{node}.1;'
        return template

    def genDummy(self,id,privateKey,targets=[]):
        template = f'''[Interface]
        Address = 127.11.11.11/32
        ListenPort = 52820
        PrivateKey = '''+str(privateKey)
        template += f'\nPostUp =  echo 1 > /proc/sys/net/ipv4/ip_forward; echo 0 > /proc/sys/net/ipv4/conf/all/rp_filter; echo 0 > /proc/sys/net/ipv4/conf/default/rp_filter; echo "fq" > /proc/sys/net/core/default_qdisc; echo "bbr" > /proc/sys/net/ipv4/tcp_congestion_control; ip addr add 10.0.{id}.1/30 dev lo;'
        template += "iptables -t nat -A POSTROUTING -o $(ip route show default | awk '/default/ {print $5}') -j MASQUERADE;"
        template += f'ip link add vxlan251 type vxlan id 251 dstport 4789 local 10.0.{id}.1; ip link set vxlan251 up;'
        template += f'ip addr add 10.0.251.{id}/24 dev vxlan251;'
        template += self.genVXLAN(targets)
        template += f'\nPostDown = ip addr del 10.0.{id}.1/30 dev lo; ip link delete vxlan251;'
        template += '''
        SaveConfig = true'''
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
