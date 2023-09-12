import time

class Templator:

    def genServer(self,interface,config,payload,serverIP,serverPort,wgobfsSharedKey=""):
        clientPublicKey,linkType,prefix,area = payload['clientPublicKey'],payload['linkType'],payload['prefix'],payload['area']
        wgobfs,mtu = "",1412 if "v6" in interface else 1420
        if linkType == "wgobfs": wgobfs += f"sudo iptables -t mangle -I INPUT -p udp -m udp --dport {serverPort} -j WGOBFS --key {wgobfsSharedKey} --unobfs;\n"
        if linkType == "wgobfs": wgobfs += f"sudo iptables -t mangle -I OUTPUT -p udp -m udp --sport {serverPort} -j WGOBFS --key {wgobfsSharedKey} --obfs;\n"
        wgobfsReverse = wgobfs.replace("mangle -I","mangle -D")
        template = f'''#!/bin/bash
#Area {area}
if [ "$1" == "up" ];  then
    {wgobfs}
    sudo ip link add dev {interface} type wireguard
    sudo ip address add dev {interface} {prefix}{config["id"]}.{serverIP}/31
    sudo ip -6 address add dev {interface} fe82:{config["id"]}::{serverIP}/127
    sudo wg set {interface} listen-port {serverPort} private-key /opt/wg-mesh/links/{interface}.key peer {clientPublicKey} preshared-key /opt/wg-mesh/links/{interface}.pre allowed-ips 0.0.0.0/0,::0/0
    sudo ip link set {interface} mtu {mtu}
    sudo ip link set up dev {interface}
else
    {wgobfsReverse}
    sudo ip link delete dev {interface}
fi'''
        return template

    def genClient(self,interface,config,resp,serverIPExternal,linkType="default",wgobfsSharedKey="",prefix="10.0.",):
        serverID,serverIP,serverPort,serverPublicKey = resp['id'],resp['lastbyte'],resp['port'],resp['publicKeyServer']
        wgobfs,mtu = "",1412 if "v6" in interface else 1420
        if linkType == "wgobfs": wgobfs += f"sudo iptables -t mangle -I INPUT -p udp -m udp --sport {serverPort} -j WGOBFS --key {wgobfsSharedKey} --unobfs;\n"
        if linkType == "wgobfs": wgobfs += f"sudo iptables -t mangle -I OUTPUT -p udp -m udp --dport {serverPort} -j WGOBFS --key {wgobfsSharedKey} --obfs;\n"
        wgobfsReverse = wgobfs.replace("mangle -I","mangle -D")
        template = f'''#!/bin/bash
#Area {config['bird']["area"]}
if [ "$1" == "up" ];  then
    {wgobfs}
    sudo ip link add dev {interface} type wireguard
    sudo ip address add dev {interface} {prefix}{serverID}.{int(serverIP)+1}/31
    sudo ip -6 address add dev {interface} fe82:{serverID}::{int(serverIP)+1}/127
    sudo wg set {interface} private-key /opt/wg-mesh/links/{interface}.key peer {serverPublicKey} preshared-key /opt/wg-mesh/links/{interface}.pre allowed-ips 0.0.0.0/0,::0/0 endpoint {serverIPExternal}:{serverPort}
    sudo ip link set {interface} mtu {mtu}
    sudo ip link set up dev {interface}
else
    {wgobfsReverse}
    sudo ip link delete dev {interface}
fi'''
        return template

    def genDummy(self,serverID,connectivity):
        masquerade = ""
        if connectivity['ipv4']: masquerade += "sudo iptables -t nat -A POSTROUTING -o $(ip route show default | awk '/default/ {{print $5}}' | tail -1) -j MASQUERADE;\n"
        if connectivity['ipv6']: masquerade += "sudo ip6tables -t nat -A POSTROUTING -o $(ip -6 route show default | awk '/default/ {{print $5}}' | tail -1) -j MASQUERADE;\n"
        masqueradeReverse = masquerade.replace("-A POSTROUTING","-D POSTROUTING")
        template = f'''#!/bin/bash
if [ "$1" == "up" ];  then
    {masquerade}
    sudo ip addr add 10.0.{serverID}.1/30 dev lo;
    sudo ip -6 addr add fd10:0:{serverID}::1/48 dev lo;
    sudo ip link add vxlan1 type vxlan id 1 dstport 1789 local 10.0.{serverID}.1;
    sudo ip -6 link add vxlan1v6 type vxlan id 2 dstport 1790 local fd10:0:{serverID}::1;
    sudo ip link set vxlan1 up; sudo ip -6 link set vxlan1v6 up;
    sudo ip addr add 10.0.251.{serverID}/24 dev vxlan1;
    sudo ip -6 addr add fd10:251::{serverID}/64 dev vxlan1v6;
else
    {masqueradeReverse}
    sudo ip addr del 10.0.{serverID}.1/30 dev lo;
    sudo ip -6 addr del fd10:0:{serverID}::1/48 dev lo;
    sudo ip link delete vxlan1; sudo ip -6 link delete vxlan1v6;
fi'''
        return template

    def genVXLAN(self,targets):
        template = ""
        for node in targets: template += f'bridge fdb append 00:00:00:00:00:00 dev vxlan251 dst 10.0.{node}.1;'
        return template
    
    def getFirst(self,latency):
        for area,latencyData in latency.items():
            for entry in latencyData: return entry

    def genBird(self,latency,local,config):
        firstNode = self.getFirst(latency)
        if not firstNode: return ""
        if not local:
            routerID = latency[firstNode]["origin"]
        else:
            routerID = local[0][0]
        template = f'''log syslog all;
router id {routerID}; #updated '''+str(int(time.time()))+'''

protocol device {
    scan time 10;
}
'''
        localPTP = ""
        for area,latencyData in latency.items():
            for target,data in latencyData.items():
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
    ipv6;
    interface "lo";
    interface "tunnel*";
}

protocol static {
    ipv4;
    include "static.conf";
}

include "bgp.conf";

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
    tick '''+str(config['bird']['tick'])+''';
    graceful restart yes;
    ipv4 {
        import all;
        export filter export_OSPF;
    };'''
        for area,latencyData in latency.items():
            template += """
    area """+str(area)+""" {"""
            if config['bird']['client']: template += "\n\tstub router;\n"
            for target,data in latencyData.items():
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
    };"""
        template += """
}"""
        if config['bird']['ospfv3']:
            template += """
filter export_OSPFv3 {
    if (net.len > 48) then reject;
    if source ~ [ RTS_DEVICE, RTS_STATIC ] then accept;
    reject;
}
protocol ospf v3 {
    tick """+str(config['bird']['tick'])+""";
    graceful restart yes;
    ipv6 {
        export filter export_OSPFv3;
    };"""
            for area,latencyData in latency.items():
                template += """
    area """+str(area)+""" {"""
                if config['bird']['client']: template += "\n\tstub router;\n"
                for target,data in latencyData.items():
                    template += '''
        interface "'''+target+'''" {
            type ptmp;
            cost '''+str(data["latency"])+'''; #'''+data["target"]+'''
        };
            '''
                template += """
    };"""
            template += """
}"""
        
        return template
