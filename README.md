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
- [x] Port Optimizer for lowest Ping
 
Tested on Debian 11 with systemd.<br>
Works fine on KVM or Dedis however Containers such as OVZ or LXC have issues with bird and/or wireguard.<br>

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
cat /opt/wg-mesh/token
```
Connect Node2 to Node1
```
su wg-mesh -c "/opt/wg-mesh/cli.py connect http://<node2IP>:8080 <token>"
```
After connecting successfully, a dummy.sh will be created, which assigns a 10.0.nodeID.1/30 to lo.<br>
This will be picked up by bird, so on booth nodes on 10.0.1.1 and 10.0.2.1 should be reachable after bird ran.<br>
Regarding NAT or in general behind Firewalls, the "connector" is always a Client, the endpoint the Server.<br>

**Example 2+ nodes**<br>
```
#Install wg-mesh and initialize the first node
curl -so- https://raw.githubusercontent.com/Ne00n/wg-mesh/experimental/install.sh | bash -s -- init 1 public
#Install wg-mesh and initialize the second node
curl -so- https://raw.githubusercontent.com/Ne00n/wg-mesh/experimental/install.sh | bash -s -- init 2
#Install wg-mesh and initialize the third node
curl -so- https://raw.githubusercontent.com/Ne00n/wg-mesh/experimental/install.sh | bash -s -- init 3
```
Grab the Token from Node1 with
```
cat /opt/wg-mesh/token
```
Connect Node2 to Node1
```
su wg-mesh -c "/opt/wg-mesh/cli.py connect http://<node1IP>:8080 <token>"
```
Connect Node3 to Node1
```
su wg-mesh -c "/opt/wg-mesh/cli.py connect http://<node1IP>:8080 <token>"
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
- /connectivity needs a valid token, otherwise will refuse to provide connectivity info<br>
Internal requests from 10.0.0.0/8 don't need a token.
- /connect needs a valid token, otherwise the service will refuse to setup a wg link<br>
Internal requests from 10.0.0.0/8 don't need a token.
- /update needs a validate token, otherwise will not update port of wg link<br>
Internal requests from 10.0.0.0/8 don't need a token.
- /disconnect needs a valid wg public key and link name, otherwise will refuse to disconnect a specific link<br>

**Shutdown/Startup**
```
su wg-mesh -c "/opt/wg-mesh/cli.py down"
su wg-mesh -c "/opt/wg-mesh/cli.py up" && systemctl restart wgmesh
```

**Disconnect**<br>
To disconnect all links on a Node
```
su wg-mesh -c "/opt/wg-mesh/cli.py disconnect"
#shutdown and remove a link despite untable to reach API endpoint
su wg-mesh -c "/opt/wg-mesh/cli.py disconnect force"
#disconnect a specific link
su wg-mesh -c "/opt/wg-mesh/cli.py disconnect pipe250"
#disconnect a specific link with force
su wg-mesh -c "/opt/wg-mesh/cli.py disconnect pipe250 force"
```

**Removal**
```
su wg-mesh -c "/opt/wg-mesh/cli.py down" && bash /opt/wg-mesh/deinstall.sh
```

**Updating**
```
su wg-mesh -c "cd /opt/wg-mesh/; git pull" && systemctl restart wgmesh && systemctl restart wgmesh-bird
```
**Limitations**<br>
Connecting multiple nodes at once, without waiting for the other node to finish, will result in double links.<br>
By default, when a new node joins, it checks which connections it does not have, which with a new node would be everything.<br>

Additional, bird2, by default, takes 30s to distribute the routes, there will be also a delay.<br>
In total roughtly 60s, depending on the network size, to avoid this issue.<br>

Depending on network conditions, bird will be reloaded, every 5 minutes or as short as every 10 seconds.
This will drop long lived TCP connections.

**Known Issues**<br>
- Remvoing wg-mesh without prior disconnecting active links, will result in broken links until restarted.<br>
- A client that does not have a direct connection to a newly added server, is stuck with a old outdated vxlan configuration.<br> 
This can be fixed by reloading wgmesh-bird.<br>

**Troubleshooting**
- You can check the logs/<br>
- wg-mesh is very slow<br>
sudo requires a resolvable hostname
- wg-mesh is not meshing<br>
bird2 needs to be running / hidepid can block said access to check if bird is running.<br>
- RTNETLINK answers: Address already in use<br>
Can also mean the Port wg tries to listen, is already in use. Check your existing wg links.<br>
- duplicate vxlan mac address / vxlan mac flapping<br>
If you are using a virtual machine, check your machine-id if they are the same.<br>
You can check it with or tools/machine-id.py<br>
```
cat /etc/machine-id
```
Which can be easily fixed by running.<br>
```
rm -f /etc/machine-id && rm -f /var/lib/dbus/machine-id
dbus-uuidgen --ensure && systemd-machine-id-setup
reboot
```