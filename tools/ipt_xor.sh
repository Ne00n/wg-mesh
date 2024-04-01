#!/bin/bash
apt-get update
apt-get install linux-headers-$(uname -r) git make autoconf automake libtool libxtables-dev pkg-config -y
git clone https://github.com/faicker/ipt_xor
cd ipt_xor
cd kernel
make
sudo make install
insmod xt_XOR.ko
echo 'ipt_xor' > /etc/modules
