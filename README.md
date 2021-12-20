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

**Features (Planned)**<br />
- join nodes with simple cli command
- automatic mesh buildup when node has joined
- dualstack and/or singlestack (v4/v6)
- remove nodes

**Features**<br />
- TBA

**Todo**<br />
- everything

**Setup**<br />
- TBA

**Example**<br />
Initialize the first Node<br>
```
./wg-mesh.py init Node1 1
```
Generate the Wireguard files for the Client/Server
```
./wg-mesh.py join Node2
```
Connect Node2 to Node1
```
TBA
```