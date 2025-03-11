## Peering

Peering works like Connect, its technically the same.<br>
For example.<br>

```
wgmesh peer https://myendpoint.com:443 peertoken
```

A BGP session will be setup automatically on booth ends.<br>

However, since filters are used, you have to specify which prefixes should be imported.<br>
You can simply do this with.<br>
```
wgmesh set AllowedPeers 10.1.0.0/16
```
You can add multiple subnets and you can remove them the same way you added them.<br>
Don't forget to restart the services.<br>