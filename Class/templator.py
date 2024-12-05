import time

class Templator:

    def genServer(self,interface,config,payload,serverIP,serverPort,wgobfsSharedKey=""):
        clientPublicKey,linkType,prefix,area,connectivity = payload['clientPublicKey'],payload['linkType'],payload['prefix'],payload['area'],payload['connectivity']
        wgobfs,mtu = "",1412 if "v6" in interface else 1420
        wgPrefix = "awg" if linkType == "amneziawg" else "wg"
        wgProtocol = "amneziawg" if linkType == "amneziawg" else "wireguard"
        if linkType == "wgobfs": wgobfs += f"sudo iptables -t mangle -I INPUT -p udp -m udp --dport {serverPort} -j WGOBFS --key {wgobfsSharedKey} --unobfs;\n"
        if linkType == "wgobfs": wgobfs += f"sudo iptables -t mangle -I OUTPUT -p udp -m udp --sport {serverPort} -j WGOBFS --key {wgobfsSharedKey} --obfs;\n"
        if linkType == "ipt_xor" and not "v6" in interface: wgobfs += f'sudo iptables -t mangle -I OUTPUT -p udp -d {connectivity["ipv4"]} -j XOR --keys "{wgobfsSharedKey}";\n'
        if linkType == "ipt_xor" and not "v6" in interface: wgobfs += f'sudo iptables -t mangle -I INPUT -p udp -s {connectivity["ipv4"]} -j XOR --keys "{wgobfsSharedKey}";\n'
        wgobfsReverse = wgobfs.replace("mangle -I","mangle -D")
        template = f'''#!/bin/bash
#Area {area}
#Peer {prefix}.{config["id"]}.1
if [ "$1" == "up" ];  then
    {wgobfs}
    sudo ip link add dev {interface} type {wgProtocol}
    sudo ip address add dev {interface} {prefix}.{config["id"]}.{serverIP}/31
    sudo ip -6 address add dev {interface} fe82:{config["id"]}::{serverIP}/127
    sudo {wgPrefix} set {interface} listen-port {serverPort} private-key /opt/wg-mesh/links/{interface}.key peer {clientPublicKey} preshared-key /opt/wg-mesh/links/{interface}.pre allowed-ips 0.0.0.0/0,::0/0
    sudo ip link set {interface} mtu {mtu}
    sudo ip link set up dev {interface}
else
    {wgobfsReverse}
    sudo ip link delete dev {interface}
fi'''
        return template

    def genClient(self,interface,config,resp,serverIPExternal,linkType="default",prefix="10.0",peerPrefix="172.31"):
        serverID,serverIP,serverPort,serverPublicKey,wgobfsSharedKey = resp['id'],resp['lastbyte'],resp['port'],resp['publicKeyServer'],resp['wgobfsSharedKey']
        wgobfs,mtu = "",1412 if "v6" in interface else 1420
        wgPrefix = "awg" if linkType == "amneziawg" else "wg"
        wgProtocol = "amneziawg" if linkType == "amneziawg" else "wireguard"
        if linkType == "wgobfs": wgobfs += f"sudo iptables -t mangle -I INPUT -p udp -m udp --sport {serverPort} -j WGOBFS --key {wgobfsSharedKey} --unobfs;\n"
        if linkType == "wgobfs": wgobfs += f"sudo iptables -t mangle -I OUTPUT -p udp -m udp --dport {serverPort} -j WGOBFS --key {wgobfsSharedKey} --obfs;\n"
        if linkType == "ipt_xor" and not "v6" in interface: wgobfs += f'sudo iptables -t mangle -I OUTPUT -p udp -d {serverIPExternal} -j XOR --keys "{wgobfsSharedKey}";\n'
        if linkType == "ipt_xor" and not "v6" in interface: wgobfs += f'sudo iptables -t mangle -I INPUT -p udp -s {serverIPExternal} -j XOR --keys "{wgobfsSharedKey}";\n'
        wgobfsReverse = wgobfs.replace("mangle -I","mangle -D")
        template = f'''#!/bin/bash
#Area {config['bird']["area"]}
#Peer {peerPrefix}.{serverID}.1
if [ "$1" == "up" ];  then
    {wgobfs}
    sudo ip link add dev {interface} type {wgProtocol}
    sudo ip address add dev {interface} {prefix}.{serverID}.{int(serverIP)+1}/31
    sudo ip -6 address add dev {interface} fe82:{serverID}::{int(serverIP)+1}/127
    sudo {wgPrefix} set {interface} private-key /opt/wg-mesh/links/{interface}.key peer {serverPublicKey} preshared-key /opt/wg-mesh/links/{interface}.pre allowed-ips 0.0.0.0/0,::0/0 endpoint {serverIPExternal}:{serverPort}
    sudo ip link set {interface} mtu {mtu}
    sudo ip link set up dev {interface}
else
    {wgobfsReverse}
    sudo ip link delete dev {interface}
fi'''
        return template

    def genDummy(self,config,connectivity):
        serverID = int(config['id'])
        serverID += config['vxlanOffset']
        #has to be done better at some point
        subnet, host = config['subnetVXLAN'].split("/")
        sSubnet = subnet.split(".")
        prefix = f"{sSubnet[0]}.{sSubnet[1]}"
        subnet = f"{sSubnet[0]}.{sSubnet[1]}.{sSubnet[2]}"
        vxlanSubnet = f"{subnet}.{serverID}/{host}"
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
    sudo ip addr add {vxlanSubnet} dev vxlan1;
    sudo ip -6 addr add fd10:251::{serverID}/64 dev vxlan1v6;
else
    {masqueradeReverse}
    sudo ip addr del {prefix}.{serverID}.1/30 dev lo;
    sudo ip -6 addr del fd10:0:{serverID}::1/48 dev lo;
    sudo ip link delete vxlan1; sudo ip -6 link delete vxlan1v6;
fi'''
        return template

    def genBGPPeer(self,subnetPrefix,peer):
        export = f"{subnetPrefix}.0.0/16"
        return '''
protocol bgp '''+peer["nic"]+''' {
        ipv4 {
                preference 175;
                import all;
                export where net ~ [ '''+export+''' ];
        };
        local as '''+"".join(peer["origin"].split(".")[2:])+''';
        neighbor '''+peer["target"]+''' as '''+"".join(peer["target"].split(".")[2:])+''';
}
        '''

    def genInterfaceOSPF(self,data,ospfType=2):
        nic = data['nic']
        template = f'\n\t\tinterface "{nic}" {{' 
        template += '\n\t\t\tstub;' if "Peer" in data ['nic'] else '\n\t\t\ttype ptmp;'
        if ospfType == 2 and not "Peer" in data['nic']: template += f"\n\t\t\tneighbors {{ {data['target']}; }};"
        template += f"\n\t\t\tcost {data['cost']};\n\t\t}};"
        return template

    def genBird(self,latency,peers,config):
        isRouter = "yes" if config['bird']['client'] else "no"
        subnetPrefix = ".".join(config['subnet'].split(".")[:2])
        routerID = f"{subnetPrefix}.{config['id']}.1"
        logLevels = f"{config['bird']['loglevel']}"
        template = f'log "/etc/bird/bird.log" {logLevels};\nrouter id {routerID}; #generated {int(time.time())}'
        template += "\n\nprotocol device {\n\tscan time 10;\n}\n"

        localPTP = ""
        for area,latencyData in latency.items():
            for data in latencyData:
                if localPTP != "":
                    localPTP += ","
                localPTP += data['target']+"/32-"

        template += f"\nfunction avoid_local_ptp() {{\n\t### Avoid fucking around with direct peers\n\treturn net ~ [ {localPTP} ];\n}}"
        template += '\n\nprotocol direct {\n\tipv4;\n\tipv6;\n\tinterface "lo";\n\tinterface "tunnel*";\n}'
        template += f'\n\nprotocol static {{\n\tipv4;\n\troute {subnetPrefix}.0.0/16 unreachable;\n\tinclude "static.conf";\n\n}}'
        template += '\ninclude "bgp.conf";'

        #BGP Peers
        for peer in peers:
            template += self.genBGPPeer(subnetPrefix,peer)

        template += "\nprotocol kernel {\n\tipv4 {\n\t\texport filter { "
        template += f"\n\t\t\tkrt_prefsrc = {routerID};"
        template += "\n\t\t\tif avoid_local_ptp() then reject;\n\t\t\taccept;\n\t\t};\n\t};\n}"
        template += "\n\nprotocol kernel {\n\tipv6 { export all; };\n}"

        if config['bird']['ospfv2']:
            template += "\n\nfilter export_OSPF {\n\tif source ~ [ RTS_DEVICE ] then accept;"
            for peerSubnet in config['AllowedPeers']:
                template += f"\n\tif net ~ [ {peerSubnet} ] then accept;" 
            template += "\n\treject;\n}"
            template += f"\n\nprotocol ospf {{\n\ttick {config['bird']['tick']};\n\tgraceful restart yes;\n\tstub router {isRouter};"
            template += f"\n\tipv4 {{\n\t\timport all;\n\t\texport filter export_OSPF;\n\t}};"
            for area,latencyData in latency.items():
                template += f"\n\tarea {area} {{"
                for data in latencyData:
                    template += self.genInterfaceOSPF(data)
                template += "\n\t};"
            template += "\n}"

        if config['bird']['ospfv3']:
            template += f"\n\nfilter export_OSPFv3 {{\n\tif (net.len > 48) then reject;\n\tif source ~ [ RTS_DEVICE, RTS_STATIC ] then accept;\n\treject;\n}}"
            template += f"\n\nprotocol ospf v3 {{\n\ttick {config['bird']['tick']};\n\tgraceful restart yes;\n\tstub router {isRouter};"
            template += f"\n\tipv6 {{\n\t\texport filter export_OSPFv3;\n\t}};"
            for area,latencyData in latency.items():
                template += f"\n\tarea {area} {{"
                for data in latencyData:
                    template += self.genInterfaceOSPF(data,3)
                template += "\n\t};"
            template += "\n}\n"
        
        return template
