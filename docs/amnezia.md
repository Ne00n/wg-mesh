## amneziawg

This is currently untested however supported technically.

Install amneziawg with
```
bash /opt/wg-mesh/tools/amnezia.sh
```
To enable amneziawg connections run.<br>
```
#add amneziawg to linkTypes
wgmesh enable amneziawg 
#To override the defaultLinkType, if you want to prefer amneziawg over normal wg.
wgmesh set defaultLinkType amneziawg
systemctl restart wgmesh
```

If the remote has amneziawg not in linkeTypes, default will be used.<br>