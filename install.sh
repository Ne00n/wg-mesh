#!/bin/bash
if [[ $(id -u) -ne 0 ]] ; then echo "Please run as root" ; exit 1 ; fi
apt-get install wireguard bird2 sudo python3 python3-pip fping git -y
pip3 install netaddr requests bottle gunicorn gevent
cd /opt/
#git
git clone https://github.com/Ne00n/wg-mesh.git
cd wg-mesh
useradd wg-mesh -r -d /opt/wg-mesh -s /bin/bash
#run init
./cli.py $@
chown -R wg-mesh:wg-mesh /opt/wg-mesh/
chmod -R 700 /opt/wg-mesh/
#sudo permissions
echo "wg-mesh ALL=(ALL) NOPASSWD: /sbin/ip*" >> /etc/sudoers.d/wg-mesh
echo "wg-mesh ALL=(ALL) NOPASSWD: /usr/sbin/ip*" >> /etc/sudoers.d/wg-mesh
echo "wg-mesh ALL=(ALL) NOPASSWD: /sbin/bridge fdb append *" >> /etc/sudoers.d/wg-mesh
echo "wg-mesh ALL=(ALL) NOPASSWD: /usr/sbin/bridge fdb append *" >> /etc/sudoers.d/wg-mesh
echo "wg-mesh ALL=(ALL) NOPASSWD: /usr/bin/wg set*" >> /etc/sudoers.d/wg-mesh
#bird permissions
echo "wg-mesh ALL=(ALL) NOPASSWD: /bin/systemctl reload bird" >> /etc/sudoers.d/wg-mesh
echo "wg-mesh ALL=(ALL) NOPASSWD: /usr/bin/systemctl reload bird" >> /etc/sudoers.d/wg-mesh
usermod -a -G bird wg-mesh
chmod -R 770 /etc/bird/
#sysctl
echo "net.ipv4.ip_forward=1" >> /etc/sysctl.d/wg-mesh.conf
echo "net.ipv4.conf.all.rp_filter=0" >> /etc/sysctl.d/wg-mesh.conf
echo "net.ipv4.conf.default.rp_filter=0" >> /etc/sysctl.d/wg-mesh.conf
echo "net.core.default_qdisc=fq " >> /etc/sysctl.d/wg-mesh.conf
echo "net.ipv4.tcp_congestion_control=bbr" >> /etc/sysctl.d/wg-mesh.conf
sysctl --system
#systemd wg-mesh service
cp /opt/wg-mesh/configs/wgmesh.service /etc/systemd/system/wgmesh.service
systemctl enable wgmesh && systemctl start wgmesh
#systemd bird service
cp /opt/wg-mesh/configs/wgmesh-bird.service /etc/systemd/system/wgmesh-bird.service
systemctl enable wgmesh-bird && systemctl start wgmesh-bird
#systemd pipe service
cp /opt/wg-mesh/configs/wgmesh-pipe.service /etc/systemd/system/wgmesh-pipe.service
systemctl enable wgmesh-pipe