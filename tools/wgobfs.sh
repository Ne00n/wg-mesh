#!/bin/bash
apt-get install linux-headers-$(uname -r) git autoconf libtool libxtables-dev pkg-config -y
#git clone https://github.com/Ne00n/xt_wgobfs.git
git clone https://github.com/infinet/xt_wgobfs
cd xt_wgobfs
./autogen.sh
./configure
make
sudo make install
depmod -a && modprobe xt_WGOBFS