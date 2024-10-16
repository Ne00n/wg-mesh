#!/bin/bash
set -e
apt install -y software-properties-common python3-launchpadlib gnupg2 linux-headers-$(uname -r)
apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 57290828
echo "deb https://ppa.launchpadcontent.net/amnezia/ppa/ubuntu focal main" | sudo tee -a /etc/apt/sources.list
echo "deb-src https://ppa.launchpadcontent.net/amnezia/ppa/ubuntu focal main" | sudo tee -a /etc/apt/sources.list
apt-get update
apt-get install -y amneziawg
echo "wg-mesh ALL=(ALL) NOPASSWD: /usr/bin/awg set*" >> /etc/sudoers.d/wg-mesh