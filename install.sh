#!/bin/bash
apt-get install wireguard bird2 python3 fping git -y
cd /root/
git clone https://github.com/Ne00n/wg-mesh.git
cd wg-mesh
if [ "$1" != "install" ];  then
./wg-mesh.py $@
fi