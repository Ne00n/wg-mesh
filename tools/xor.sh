#!/bin/bash
set -e
cd
apt-get update
apt-get install linux-headers-$(uname -r) git make autoconf automake libtool libxtables-dev pkg-config -y
git clone https://github.com/faicker/ipt_xor
#https://github.com/Ne00n/ipt_xor
cd ipt_xor
cd userspace
make libxt_XOR.so
cp libxt_XOR.so /usr/lib/x86_64-linux-gnu/xtables/
cd ..
cd kernel
make
insmod xt_XOR.ko
currentKernel=$(uname -r)
cp xt_XOR.ko /lib/modules/$currentKernel/kernel/net/netfilter/
lsmod | grep "xt_XOR"