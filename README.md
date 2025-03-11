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
- By default 10.0.x.x/16.<br>
- 10.0.id.1 Node /30<br>
- 10.0.id.4-255 peers /31<br>
- 10.0.251.1-255 vxlan /32<br>

**Features**<br>
- [x] automatic mesh buildup when node has joined
- [x] join nodes via cli
- [x] disconnect nodes via cli
- [x] VXLAN
- [x] Dualstack and/or Singlestack (Transport)
- [x] Dualstack (within the VPN Network)
- [x] Autostart Wireguard links on boot
- [x] Active Latency optimisation
- [x] Packet loss detection & rerouting
- [x] High Jitter detection & rerouting
- [x] Support for wgobfs, ipt_xor and AmneziaWG
- [x] Push notifications via gotify

**Requirements**<br>
- Debian or Ubuntu
- Python 3.9 or higher
- Kernel 5.4+ (wg kernel module, no user space support)

Keep in mind that some containers such as OVZ or LXC, depending on kernel version and host configuration have issues with bird and/or wireguard.<br>

**Example 2 nodes**<br>
The ID needs to be unique, otherwise it will result in collisions.<br>
Keep in mind, ID's 200 and higher are reserved for clients, they won't get meshed.<br>

Public is used to expose the API to all interfaces, by default it listens only local on 10.0.id.1.<br>
Use Public only for testing! since everything is transmitted unencrypted, otherwise use a reverse proxy with TLS.<br>

Depending on what Subnet you are using, you either have to increment the ID's by 2 (10.) or by 1 (192/172.)<br>
If 10.0.x.x/16 is used (default), a /23 is reserved per node, hence you have to increment it by 2.<br>
```
#Install wg-mesh and initialize the first node
curl -so- https://raw.githubusercontent.com/Ne00n/wg-mesh/experimental/install.sh | bash -s -- init 0 public
#Install wg-mesh and initialize the second node
curl -so- https://raw.githubusercontent.com/Ne00n/wg-mesh/experimental/install.sh | bash -s -- init 2
```
Grab the Token from Node 0<br>
```
wgmesh token
```
Connect Node 2 to Node 0
```
wgmesh connect http://<node0IP>:8080 <token>
```
After connecting successfully, a dummy.sh will be created, which assigns a 10.0.nodeID.0/30 to lo.<br>
This will be picked up by bird, so on booth nodes on 10.0.0.1 and 10.0.2.1 should be reachable after bird ran.<br>
Regarding NAT or in general behind Firewalls, the "connector" is always a Client, the endpoint the Server.<br>

**Example 2+ nodes**<br>
```
#Install wg-mesh and initialize the first node
curl -so- https://raw.githubusercontent.com/Ne00n/wg-mesh/experimental/install.sh | bash -s -- init 0 public
#Install wg-mesh and initialize the second node
curl -so- https://raw.githubusercontent.com/Ne00n/wg-mesh/experimental/install.sh | bash -s -- init 2
#Install wg-mesh and initialize the third node
curl -so- https://raw.githubusercontent.com/Ne00n/wg-mesh/experimental/install.sh | bash -s -- init 4
```
Grab the Token from Node 0 with 
```
wgmesh token
```
Connect Node 2 to Node 0
```
wgmesh connect http://<node0IP>:8080 <token>
```
Before you connect the 3rd node, make sure Node 2 already has fully connected.<br>
Connect Node 4 to Node 0
```
wgmesh connect http://<node0IP>:8080 <token>
```
Wait for bird to pickup all routes + mesh buildup.<br>
You can check it with<br>
```
birdc show route
#and/or
cat /opt/wg-mesh/configs/state.json
```
All 3 nodes should be reachable under 10.0.nodeID.1<br>

**Removal**
```
wgmesh down && bash /opt/wg-mesh/deinstall.sh
```

**Updating**
```
wgmesh update && wgmesh migrate && systemctl restart wgmesh && systemctl restart wgmesh-bird
```

**Limitations**<br>
Connecting multiple nodes at once, without waiting for the other node to finish, will result in double links.<br>
By default, when a new node joins, it checks which connections it does not have, which with a new node would be everything.<br>

Additional, bird2, by default, takes 30s to distribute the routes, there will be also a delay.<br>
In total roughtly 60s, depending on the network size, to avoid this issue.<br>

Depending on network conditions, bird will be reloaded, every 5 minutes or as short as every 20 seconds.<br>
This will drop long lived TCP connections.

**Known Issues**<br>
- A client that does not have a direct connection to a newly added server, is stuck with a old outdated vxlan configuration.<br> 
This can be "fixed" by reloading wgmesh-bird.<br>