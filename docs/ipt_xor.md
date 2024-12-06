## ipt_xor

Github repository: https://github.com/faicker/ipt_xor<br>

Install ipt_xor with
```
bash /opt/wg-mesh/tools/xor.sh
```
To enable ipt_xor connections run.<br>
```
#add ipt_xor to linkTypes
wgmesh ipt_xor wgobfs 
#To override the defaultLinkType, if you want to prefer wgobfs over normal wg.
wgmesh set defaultLinkType ipt_xor
systemctl restart wgmesh
```

If the remote has ipt_xor not in linkeTypes, default will be used.<br>