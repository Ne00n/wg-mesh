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
- wireguard (vpn)
- bird2 (routing)

**Planned**<br />
- automatic mesh buildup when node has joined
- dualstack and/or singlestack (v4/v6)

**Features**<br />
- join nodes via cli
- disconnect nodes via cli

This has been build for Debian and Ubuntu.<br>
Works fine on KVM or Dedis however Containers such as OVZ or LXC have issues with bird and/or wireguard.<br>

**Example 2 nodes**<br />
Install wg-mesh and initialize the first node<br>
```
curl -so- https://raw.githubusercontent.com/Ne00n/wg-mesh/master/install.sh | bash -s -- init Node1 1
```
- The ID and the Name needs to be unique, otherwise it will result in collisions<br>
Install wg-mesh and initialize the second node<br>
```
curl -so- https://raw.githubusercontent.com/Ne00n/wg-mesh/master/install.sh | bash -s -- init Node2 2
```
Connect Node1 to Node2
```
python3 cli.py connect <Node2IP> <token>
```
You can find the Token in /opt/wg-mesh/token<br>
After connecting successfully, a dummy.sh will be created, which assigns a 10.0.nodeID.1/30 to lo.<br>
This will be picked up by bird, so on booth nodes on 10.0.1.1 and 10.0.2.1 should be reachable after bird ran.<br>

**Disconnect**
To disconnect all links on a Node
```
python3 cli.py disconnect
```

**Deinstall**
```
curl -so- https://raw.githubusercontent.com/Ne00n/wg-mesh/master/deinstall.sh | bash
```