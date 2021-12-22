# wg-mesh
## Work in Progress

**Idea**<br />
- Build a [wireguard](https://www.wireguard.com/) mesh vpn in [tinc](https://www.tinc-vpn.org/) style
- Simple CLI to add and manage nodes
- Replacement for https://github.com/Ne00n/pipe-builder-3000/

**Software**<br />
- python3
- wireguard
- bird2

**Planned**<br />
- automatic mesh buildup when node has joined
- dualstack and/or singlestack (v4/v6)
- remove nodes

**Features**<br />
- join nodes with simple cli command

**Todo**<br />
- everything

**Example 2 nodes**<br />
Install wg-mesh and initialize the first node<br>
```
curl -so- https://raw.githubusercontent.com/Ne00n/wg-mesh/master/install.sh | bash -s -- init Node 1
```
Generate the Wireguard files for the Client/Server
```
./wg-mesh.py join Node2
```
Connect Node2 to Node1
```
curl -so- https://raw.githubusercontent.com/Ne00n/wg-mesh/master/install.sh | bash -s -- connect...
```