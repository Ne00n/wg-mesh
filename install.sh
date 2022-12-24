#!/bin/bash
if [[ $(id -u) -ne 0 ]] ; then echo "Please run as root" ; exit 1 ; fi
apt-get install wireguard bird2 sudo python3 python3-pip fping git -y
pip3 install netaddr
pip3 install requests
cd /opt/
#git
git clone https://github.com/Ne00n/wg-mesh.git
cd wg-mesh
useradd wg-mesh -r -d /opt/wg-mesh -s /bin/bash
chown -R wg-mesh:wg-mesh /opt/wg-mesh/
chmod -R 700 /opt/wg-mesh/
#wireguard permissions
chgrp wg-mesh /etc/wireguard/
chmod 770 /etc/wireguard/
#sudo permissions
echo "wg-mesh ALL=(ALL) NOPASSWD: /bin/systemctl start wg-quick@*" >> /etc/sudoers
echo "wg-mesh ALL=(ALL) NOPASSWD: /bin/systemctl stop wg-quick@*" >> /etc/sudoers
#systemd service
echo -e "[Unit]
Description=wgmesh service
Wants=network-online.target
After=network-online.target
[Service]
User=wg-mesh
Group=wg-mesh
Type=simple
WorkingDirectory=/opt/wg-mesh
ExecStart=/usr/bin/python3 api.py
[Install]
WantedBy=multi-user.target" > /etc/systemd/system/wgmesh.service
systemctl enable wgmesh && systemctl start wgmesh
if [ "$1" == "init" ];  then
./cli.py $@
fi