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
```
#Install wg-mesh and initialize the first node
curl -so- https://raw.githubusercontent.com/Ne00n/wg-mesh/experimental/install.sh | bash -s -- init 1 public
#Install wg-mesh and initialize the second node
curl -so- https://raw.githubusercontent.com/Ne00n/wg-mesh/experimental/install.sh | bash -s -- init 2
```
Grab the Token from Node1<br>
```
wgmesh token
```
Connect Node2 to Node1
```
wgmesh connect http://<node2IP>:8080 <token>
```
After connecting successfully, a dummy.sh will be created, which assigns a 10.0.nodeID.1/30 to lo.<br>
This will be picked up by bird, so on booth nodes on 10.0.1.1 and 10.0.2.1 should be reachable after bird ran.<br>
Regarding NAT or in general behind Firewalls, the "connector" is always a Client, the endpoint the Server.<br>

**Wireguard Port**<br>
If you like to change the default wireguard port.
```
wgmesh set basePort 4000 && systemctl restart wgmesh
#or 0 for random
wgmesh set basePort 0 && systemctl restart wgmesh
```

**Prevent meshing**<br>
In case you want to stop a client/server from automatically meshing into the network.<br>
You can simply block it by creating an empty state.json.<br>
```
wgmesh disable mesh && systemctl restart wgmesh
```
This needs to be done before you connecting to the network.<br>

**Example 2+ nodes**<br>
```
#Install wg-mesh and initialize the first node
curl -so- https://raw.githubusercontent.com/Ne00n/wg-mesh/experimental/install.sh | bash -s -- init 1 public
#Install wg-mesh and initialize the second node
curl -so- https://raw.githubusercontent.com/Ne00n/wg-mesh/experimental/install.sh | bash -s -- init 2
#Install wg-mesh and initialize the third node
curl -so- https://raw.githubusercontent.com/Ne00n/wg-mesh/experimental/install.sh | bash -s -- init 3
```
Grab the Token from Node 1 with
```
wgmesh token
```
Connect Node 2 to Node 1
```
wgmesh connect http://<node1IP>:8080 <token>
```
Before you connect the 3rd node, make sure Node 2 already has fully connected.<br>
Connect Node 3 to Node 1
```
wgmesh connect http://<node1IP>:8080 <token>
```
Wait for bird to pickup all routes + mesh buildup.<br>
You can check it with<br>
```
birdc show route
#and/or
cat /opt/wg-mesh/configs/state.json
```
All 3 nodes should be reachable under 10.0.nodeID.1<br>

**API**<br>
Currently the webservice / API is exposed at ::8080, without TLS, use a reverse proxy for TLS<br>
Internal requests from 10.0.0.0/8 don't need a token (connectivity, connect and update).<br>
- /connectivity needs a valid token, otherwise will refuse to provide connectivity info<br>
- /connect needs a valid token, otherwise the service will refuse to setup a wg link<br>
- /update needs a valid wg public key and link name, otherwise it will not update the wg link<br>
- /disconnect needs a valid wg public key and link name, otherwise will refuse to disconnect a specific link<br>

**Shutdown/Startup**
```
wgmesh down
wgmesh up && systemctl restart wgmesh
```

**Disconnect**<br>
To disconnect all links on a Node
```
wgmesh disconnect
#disconnect all links despite untable to reach API endpoint
wgmesh disconnect force
#disconnect a specific link e.g pipe250, pipe250v6
wgmesh disconnect pipe250
#disconnect a specific link with force
wgmesh disconnect pipe250 force
```

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