## Troubleshooting

- You can check the logs/<br>
- wg-mesh is very slow<br>
sudo requires a resolvable hostname
- wg-mesh is not meshing<br>
bird2 needs to be running / hidepid can block said access to check if bird is running.<br>
- sudo is asking for authentication<br>
reinstall sudo, likely old config file (debian 10)<br>
- RTNETLINK answers: Address already in use<br>
Can also mean the Port wg tries to listen, is already in use. Check your existing wg links.<br>
- packetloss and/or higher latency inside the wg-mesh network but not on the uplink/network itself
wireguard needs cpu time, check the load on the machine and check if you see any CPU steal.<br>
This will likely explain what you see for example on Smokeping, you can try to reduce the links to lower the cpu usage.<br>
- duplicate vxlan mac address / vxlan mac flapping or dropped connections/packet loss<br>
If you are using a virtual machine, check your machine-id if they are the same.<br>
You can check it with or tools/machine-id.py<br>
```
cat /etc/machine-id
```
Which can be easily fixed by running.<br>
```
rm -f /etc/machine-id && rm -f /var/lib/dbus/machine-id
dbus-uuidgen --ensure && systemd-machine-id-setup
reboot
```