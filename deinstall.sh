#!/bin/bash
if [[ $(id -u) -ne 0 ]] ; then echo "Please run as root" ; exit 1 ; fi
systemctl disable wgmesh && systemctl stop wgmesh
systemctl disable wgmesh-bird && systemctl stop wgmesh-bird
userdel -r wg-mesh