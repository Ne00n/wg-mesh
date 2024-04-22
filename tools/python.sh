#!/bin/bash
set -e
if [[ $(id -u) -ne 0 ]] ; then echo "Please run as root" ; exit 1 ; fi
apt-get install wireguard iptables bird2 sudo python3 python3-netaddr python3-paste python3-bottle python3-requests python3-pip fping mtr vnstat git -y