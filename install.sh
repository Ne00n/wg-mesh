#!/bin/bash
apt-get install wireguard bird2 python3 git -y
cd /root/
git clone https://github.com/Ne00n/wg-mesh.git
cd wg-mesh
./wg-mesh.py $@