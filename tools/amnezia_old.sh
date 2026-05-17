#!/bin/bash
set -e
apt-get update
apt install -y software-properties-common python3-launchpadlib gnupg2 linux-headers-$(uname -r)
gpg --keyserver keyserver.ubuntu.com --recv-keys 75c9dd72c799870e310542e24166f2c257290828
gpg --export 75c9dd72c799870e310542e24166f2c257290828 | sudo tee /usr/share/keyrings/amnezia.gpg > /dev/null
echo "deb [signed-by=/usr/share/keyrings/amnezia.gpg] https://ppa.launchpadcontent.net/amnezia/ppa/ubuntu focal main" | sudo tee -a /etc/apt/sources.list.d/amnezia.list
echo "deb-src [signed-by=/usr/share/keyrings/amnezia.gpg] https://ppa.launchpadcontent.net/amnezia/ppa/ubuntu focal main" | sudo tee -a /etc/apt/sources.list.d/amnezia.list
apt-get update
apt-get install -y amneziawg
echo "wg-mesh ALL=(ALL) NOPASSWD: /usr/bin/awg set*" >> /etc/sudoers.d/wg-mesh