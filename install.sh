#!/bin/bash
if [[ $(id -u) -ne 0 ]] ; then echo "Please run as root" ; exit 1 ; fi
apt-get install wireguard iptables bird2 sudo python3 python3-pip fping mtr vnstat git -y
pip3 install netaddr requests bottle paste
cd /opt/
#git
git clone https://github.com/Ne00n/wg-mesh.git
cd wg-mesh
git checkout experimental
useradd wg-mesh -r -d /opt/wg-mesh -s /bin/bash
#run init
./cli.py $@
chown -R wg-mesh:wg-mesh /opt/wg-mesh/
#add wgmesh to /usr/local/bin
cat <<EOF >>/usr/local/bin/wgmesh
#!/bin/bash
su wg-mesh <<EOF2
/opt/wg-mesh/cli.py \$@
EOF2
EOF
chmod +x /usr/local/bin/wgmesh
#sudo permissions
echo "wg-mesh ALL=(ALL) NOPASSWD: /sbin/ip*" >> /etc/sudoers.d/wg-mesh
echo "wg-mesh ALL=(ALL) NOPASSWD: /usr/sbin/ip*" >> /etc/sudoers.d/wg-mesh
echo "wg-mesh ALL=(ALL) NOPASSWD: /usr/sbin/iptables*" >> /etc/sudoers.d/wg-mesh
echo "wg-mesh ALL=(ALL) NOPASSWD: /usr/sbin/ip6tables*" >> /etc/sudoers.d/wg-mesh
echo "wg-mesh ALL=(ALL) NOPASSWD: /sbin/bridge fdb append *" >> /etc/sudoers.d/wg-mesh
echo "wg-mesh ALL=(ALL) NOPASSWD: /usr/sbin/bridge fdb append *" >> /etc/sudoers.d/wg-mesh
echo "wg-mesh ALL=(ALL) NOPASSWD: /usr/bin/wg set*" >> /etc/sudoers.d/wg-mesh
#bird permissions
echo "wg-mesh ALL=(ALL) NOPASSWD: /bin/systemctl reload bird" >> /etc/sudoers.d/wg-mesh
echo "wg-mesh ALL=(ALL) NOPASSWD: /usr/bin/systemctl reload bird" >> /etc/sudoers.d/wg-mesh
usermod -a -G bird wg-mesh
touch /etc/bird/static.conf
chown bird:bird /etc/bird/static.conf
touch /etc/bird/bgp.conf
chown bird:bird /etc/bird/bgp.conf
chmod -R 770 /etc/bird/
#sysctl
echo "net.ipv4.ip_forward=1" >> /etc/sysctl.d/wg-mesh.conf
echo "net.ipv4.conf.all.rp_filter=0" >> /etc/sysctl.d/wg-mesh.conf
echo "net.ipv4.conf.default.rp_filter=0" >> /etc/sysctl.d/wg-mesh.conf
echo "net.core.default_qdisc=fq " >> /etc/sysctl.d/wg-mesh.conf
echo "net.ipv4.tcp_congestion_control=bbr" >> /etc/sysctl.d/wg-mesh.conf
echo "net.ipv6.conf.all.forwarding=1" >> /etc/sysctl.d/wg-mesh.conf
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