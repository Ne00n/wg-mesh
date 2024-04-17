import time

class Templator:

    def genServer(self,interface,config,payload,serverIP,serverPort,wgobfsSharedKey=""):
        clientPublicKey,linkType,prefix,area = payload['clientPublicKey'],payload['linkType'],payload['prefix'],payload['area']
        wgobfs,mtu = "",1412 if "v6" in interface else 1420
        if linkType == "wgobfs": wgobfs += f"sudo iptables -t mangle -I INPUT -p udp -m udp --dport {serverPort} -j WGOBFS --key {wgobfsSharedKey} --unobfs;\n"
        if linkType == "wgobfs": wgobfs += f"sudo iptables -t mangle -I OUTPUT -p udp -m udp --sport {serverPort} -j WGOBFS --key {wgobfsSharedKey} --obfs;\n"
        if linkType == "ipt_xor" and not "v6" in interface: wgobfs += f'sudo iptables -t mangle -I OUTPUT -p udp --dport {serverPort} -j XOR --keys "{wgobfsSharedKey}";\n'
        if linkType == "ipt_xor" and not "v6" in interface: wgobfs += f'sudo iptables -t mangle -I INPUT -p udp --sport {serverPort} -j XOR --keys "{wgobfsSharedKey}";\n'
        wgobfsReverse = wgobfs.replace("mangle -I","mangle -D")
        template = f'''#!/bin/bash
#Area {area}
if [ "$1" == "up" ];  then
    {wgobfs}
    sudo ip link add dev {interface} type wireguard
    sudo ip address add dev {interface} {prefix}.{config["id"]}.{serverIP}/31
    sudo ip -6 address add dev {interface} fe82:{config["id"]}::{serverIP}/127
    sudo wg set {interface} listen-port {serverPort} private-key /opt/wg-mesh/links/{interface}.key peer {clientPublicKey} preshared-key /opt/wg-mesh/links/{interface}.pre allowed-ips 0.0.0.0/0,::0/0
    sudo ip link set {interface} mtu {mtu}
    sudo ip link set up dev {interface}
else
    {wgobfsReverse}
    sudo ip link delete dev {interface}
fi'''
        return template

    def genClient(self,interface,config,resp,serverIPExternal,linkType="default",prefix="10.0",):
        serverID,serverIP,serverPort,serverPublicKey,wgobfsSharedKey = resp['id'],resp['lastbyte'],resp['port'],resp['publicKeyServer'],resp['wgobfsSharedKey']
        wgobfs,mtu = "",1412 if "v6" in interface else 1420
        if linkType == "wgobfs": wgobfs += f"sudo iptables -t mangle -I INPUT -p udp -m udp --sport {serverPort} -j WGOBFS --key {wgobfsSharedKey} --unobfs;\n"
        if linkType == "wgobfs": wgobfs += f"sudo iptables -t mangle -I OUTPUT -p udp -m udp --dport {serverPort} -j WGOBFS --key {wgobfsSharedKey} --obfs;\n"
        if linkType == "ipt_xor" and not "v6" in interface: wgobfs += f'sudo iptables -t mangle -I OUTPUT -p udp --dport {serverPort} -j XOR --keys "{wgobfsSharedKey}";\n'
        if linkType == "ipt_xor" and not "v6" in interface: wgobfs += f'sudo iptables -t mangle -I INPUT -p udp --sport {serverPort} -j XOR --keys "{wgobfsSharedKey}";\n'
        wgobfsReverse = wgobfs.replace("mangle -I","mangle -D")
        template = f'''#!/bin/bash
#Area {config['bird']["area"]}
if [ "$1" == "up" ];  then
    {wgobfs}
    sudo ip link add dev {interface} type wireguard
    sudo ip address add dev {interface} {prefix}.{serverID}.{int(serverIP)+1}/31
    sudo ip -6 address add dev {interface} fe82:{serverID}::{int(serverIP)+1}/127
    sudo wg set {interface} private-key /opt/wg-mesh/links/{interface}.key peer {serverPublicKey} preshared-key /opt/wg-mesh/links/{interface}.pre allowed-ips 0.0.0.0/0,::0/0 endpoint {serverIPExternal}:{serverPort}
    sudo ip link set {interface} mtu {mtu}
    sudo ip link set up dev {interface}
else
    {wgobfsReverse}
    sudo ip link delete dev {interface}
fi'''
        return template

    def genDummy(self,config,connectivity,prefix="10.0"):
        serverID,vxlanID = config['id'],config['vxlan']
        masquerade = ""
        if connectivity['ipv4']: masquerade += "sudo iptables -t nat -A POSTROUTING -o $(ip route show default | awk '/default/ {{print $5}}' | tail -1) -j MASQUERADE;\n"
        if connectivity['ipv6']: masquerade += "sudo ip6tables -t nat -A POSTROUTING -o $(ip -6 route show default | awk '/default/ {{print $5}}' | tail -1) -j MASQUERADE;\n"
        masqueradeReverse = masquerade.replace("-A POSTROUTING","-D POSTROUTING")
        template = f'''#!/bin/bash
if [ "$1" == "up" ];  then
    {masquerade}
    sudo ip addr add {prefix}.{serverID}.1/30 dev lo;
    sudo ip -6 addr add fd10:0:{serverID}::1/48 dev lo;
    sudo ip link add vxlan1 type vxlan id 1 dstport 1789 local {prefix}.{serverID}.1;
    sudo ip -6 link add vxlan1v6 type vxlan id 2 dstport 1790 local fd10:0:{serverID}::1;
    sudo ip link set vxlan1 up; sudo ip -6 link set vxlan1v6 up;
    sudo ip addr add {prefix}.{vxlanID}.{serverID}/24 dev vxlan1;
    sudo ip -6 addr add fd10:{vxlanID}::{serverID}/64 dev vxlan1v6;
else
    {masqueradeReverse}
    sudo ip addr del {prefix}.{serverID}.1/30 dev lo;
    sudo ip -6 addr del fd10:0:{serverID}::1/48 dev lo;
    sudo ip link delete vxlan1; sudo ip -6 link delete vxlan1v6;
fi'''
        return template

    def genBGPPeer(self,config,peer):
        subnetPrefix = ".".join(config['subnet'].split(".")[:2])
        export = f"{subnetPrefix}.{config['vxlan']}.0/24"
        return '''
protocol bgp '''+peer["nic"]+''' {
        ipv4 {
                import all;
                export where net ~ [ '''+export+''' ];
        };
        local as '''+"".join(peer["origin"].split(".")[2:])+''';
        neighbor '''+peer["target"]+''' as '''+"".join(peer["target"].split(".")[2:])+''';
}
        '''

    def genBird(self,latency,peers,config):
        isRouter = "yes" if config['bird']['client'] else "no"
        routerID = f"{'.'.join(config['subnet'].split('.')[:2])}.{config['id']}.1"
        template = f'''log syslog all;
router id {routerID}; #updated '''+str(int(time.time()))+'''

protocol device {
    scan time 10;
}
'''
        localPTP = ""
        for area,latencyData in latency.items():
            for data in latencyData:
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
    interface "vxlan*";
    interface "tunnel*";
}

protocol static {
    ipv4;
    include "static.conf";
}

include "bgp.conf";'''

        #BGP Peers
        for peer in peers:
            template += self.genBGPPeer(config,peer)

        template += '''
protocol kernel {
	ipv4 {
	    export filter { '''
        template += 'krt_prefsrc = '+routerID+';'
        for peerSubnet in config['AllowedPeers']:
            template += f"if net ~ [ {peerSubnet} ] then accept;" 
        template += '''
        if avoid_local_ptp() then reject;
            accept;
        };
    };
}

protocol kernel {
    ipv6 { export all; };
}'''

        if config['bird']['ospfv2']:
            template += '''
filter export_OSPF {
    if net ~ [ 10.0.252.0/24+ ] then reject; #Source based Routing for Clients
    if net ~ [ 172.16.0.0/24+ ] then reject; #Wireguard VPN
    if net ~ [ 127.0.0.0/8+ ] then reject; #loopback
    if source ~ [ RTS_DEVICE, RTS_STATIC ] then accept;\n'''
            for peerSubnet in config['AllowedPeers']:
                template += f"if net ~ [ {peerSubnet} ] then accept;\n" 
            template += '''
    reject;
}

protocol ospf {
    tick '''+str(config['bird']['tick'])+''';
    graceful restart yes;
    stub router '''+isRouter+''';
    ipv4 {
        import all;
        export filter export_OSPF;
    };'''
            for area,latencyData in latency.items():
                template += """
    area """+str(area)+""" {"""
                for data in latencyData:
                    template += '''
        interface "'''+str(data['nic'])+'''" {
                type ptmp;
                neighbors {
                '''+data['target']+''';
                };
                cost '''+str(data['cost'])+'''; #'''+data['target']+'''E
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
    stub router """+isRouter+""";
    ipv6 {
        export filter export_OSPFv3;
    };"""
            for area,latencyData in latency.items():
                template += """
    area """+str(area)+""" {"""
                for data in latencyData:
                    template += '''
        interface "'''+str(data['nic'])+'''" {
            type ptmp;
            cost '''+str(data['cost'])+'''; #'''+data["target"]+'''E
        };
            '''
                template += """
    };"""
            template += """
}"""
        
        return template
