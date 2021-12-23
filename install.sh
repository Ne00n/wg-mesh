#!/bin/bash
if [[ $(id -u) -ne 0 ]] ; then echo "Please run as root" ; exit 1 ; fi
apt-get install wireguard bird2 python3 python3-pip fping git -y
pip3 install netaddr
cd /opt/
git clone https://github.com/Ne00n/wg-mesh.git
cd wg-mesh
if [ "$1" != "install" ];  then
./cli.py $@
fi