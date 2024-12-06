## wgobfs

Github repository: https://github.com/infinet/xt_wgobfs<br>

Install wgbofs with
```
bash /opt/wg-mesh/tools/wgobfs.sh
```
To enable wgobfs connections run.<br>
```
#add wgobfs to linkTypes
wgmesh enable wgobfs 
#To override the defaultLinkType, if you want to prefer wgobfs over normal wg.
wgmesh set defaultLinkType wgobfs
systemctl restart wgmesh
```

If the remote has wgbofs not in linkeTypes, default will be used.<br>