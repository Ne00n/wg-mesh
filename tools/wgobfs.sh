#!/bin/bash
apt-get update
apt-get install linux-headers-$(uname -r) git make autoconf automake libtool libxtables-dev pkg-config -y
#git clone https://github.com/Ne00n/xt_wgobfs.git
git clone https://github.com/infinet/xt_wgobfs
cd xt_wgobfs
./autogen.sh
./configure
make
sudo make install
depmod -a && modprobe xt_WGOBFS
echo 'xt_WGOBFS' >> /etc/modules
