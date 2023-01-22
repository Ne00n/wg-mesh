# wg-mesh
## Work in Progress

**Idea**<br />
- Build a [wireguard](https://www.wireguard.com/) mesh vpn in [tinc](https://www.tinc-vpn.org/) style
- Simple CLI to add and manage nodes
- Replacement for https://github.com/Ne00n/pipe-builder-3000/
- Simple Token auth
- Decentralized

**Software**<br />
- python3
- wireguard (VPN)
- bird2 (Routing, OSPF)

**Network**<br />
- By default 10.0.x.x/16 is used.<br>
- 10.0.id.1 Node /30<br>
- 10.0.id.4-255 peers /31<br>
- 10.0.251.1-255 vxlan /32<br>

**Features**<br>
- [x] automatic mesh buildup when node has joined
- [x] join nodes via cli
- [x] disconnect nodes via cli
- [x] VXLAN
- [x] Dualstack and/or Singlestack (Transport)
- [ ] Dualstack (within the VPN Network)
- [ ] Support for TLS (without additional Proxy)
- [x] Autostart Wireguard links on boot
- [ ] Active Latency optimisation
- [ ] Packetloss Monitoring
 
Tested on Debian 11 with systemd.<br>
Works fine on KVM or Dedis however Containers such as OVZ or LXC have issues with bird and/or wireguard.<br>

**Example 2 nodes**<br>
```
#Install wg-mesh and initialize the first node
curl -so- https://raw.githubusercontent.com/Ne00n/wg-mesh/master/install.sh | bash -s -- init 1
#Install wg-mesh and initialize the second node
curl -so- https://raw.githubusercontent.com/Ne00n/wg-mesh/master/install.sh | bash -s -- init 2
```
The ID and the Name needs to be unique, otherwise it will result in collisions.<br>
Additionally you can add a name after the id.<br>
Grab the Token from Node2<br>
```
cat /opt/wg-mesh/token
```
Connect Node1 to Node2
```
su wg-mesh -c "/opt/wg-mesh/cli.py connect <node2IP> <token>"
```
After connecting successfully, a dummy.sh will be created, which assigns a 10.0.nodeID.1/30 to lo.<br>
This will be picked up by bird, so on booth nodes on 10.0.1.1 and 10.0.2.1 should be reachable after bird ran.<br>
Regarding NAT or in general behind Firewalls, the "connector" is always a Client, the endpoint the Server.<br>

**Example 2+ nodes**<br>
```
#Install wg-mesh and initialize the first node
curl -so- https://raw.githubusercontent.com/Ne00n/wg-mesh/master/install.sh | bash -s -- init 1
#Install wg-mesh and initialize the second node
curl -so- https://raw.githubusercontent.com/Ne00n/wg-mesh/master/install.sh | bash -s -- init 2
#Install wg-mesh and initialize the third node
curl -so- https://raw.githubusercontent.com/Ne00n/wg-mesh/master/install.sh | bash -s -- init 3
```
Grab the Token from Node1 with
```
cat /opt/wg-mesh/token
```
Connect Node2 to Node1
```
su wg-mesh -c "/opt/wg-mesh/cli.py connect <node1IP> <token>"
```
Connect Node3 to Node1
```
su wg-mesh -c "/opt/wg-mesh/cli.py connect <node1IP> <token>"
```
Wait for bird to pickup all routes + mesh buildup.<br>
You can check it with<br>
```
birdc show route
```
All 3 nodes should be reachable under 10.0.nodeID.1<br>

**API**<br>
Currently the webservice / API is exposed at ::8080, without TLS yet<br>
- /connect needs a valid token, otherwise the service will refuse to setup a wg link<br>
Internal requests from 10.0.0.0/8 don't need a token.
- /disconnect needs a valid wg public key and link name, otherwise will refuse to disconnect a specific link<br>

**Disconnect**<br>
To disconnect all links on a Node
```
su wg-mesh -c "/opt/wg-mesh/cli.py disconnect"
```

**Removal**
```
curl -so- https://raw.githubusercontent.com/Ne00n/wg-mesh/master/deinstall.sh | bash
```