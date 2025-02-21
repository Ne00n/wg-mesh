#!/bin/bash
if [[ $(id -u) -ne 0 ]] ; then echo "Please run as root" ; exit 1 ; fi
systemctl disable wgmesh && systemctl stop wgmesh
rm /etc/systemd/system/wgmesh.service
systemctl disable wgmesh-bird && systemctl stop wgmesh-bird
rm /etc/systemd/system/wgmesh-bird.service
systemctl disable wgmesh-rotate && systemctl stop wgmesh-rotate
rm /etc/systemd/system/wgmesh-rotate.service
systemctl disable wgmesh-diag && systemctl stop wgmesh-diag
rm /etc/systemd/system/wgmesh-diag.service
systemctl disable wgmesh-pipe
rm /etc/systemd/system/wgmesh-pipe.service
wgmesh down
userdel -r wg-mesh
rm /etc/sysctl.d/wg-mesh.conf
sysctl --system
rm /etc/sudoers.d/wg-mesh
rm /usr/local/bin/wgmesh