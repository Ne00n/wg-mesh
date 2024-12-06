# cli

## Init

For a quick test, you can make it listen public, however all data including wg keys are transmitted unencrypted!
```
curl -so- https://raw.githubusercontent.com/Ne00n/wg-mesh/experimental/install.sh | bash -s -- init 1 public
```

Otherwise always without public
```
curl -so- https://raw.githubusercontent.com/Ne00n/wg-mesh/experimental/install.sh | bash -s -- init 1
```
## Connect / Peer

Connect externally
```
wgmesh connect https://mahdomain.net:443 mahtoken
```

Connect internally
```
wgmesh connect http://10.0.1.1:8080
```

Connect with specific preferences (linkType , port)
```
wgmesh connect http://10.0.1.1:8080 dummy wgobfs 5555
```

If the linkType is not available or the port is already used, it will be ignored.

## Disconnect

To disconnect all links on a Node
```
wgmesh disconnect
#disconnect all links despite untable to reach API endpoint
wgmesh disconnect force
#disconnect a specific link e.g pipe250, pipe250v6
wgmesh disconnect pipe250
#disconnect a specific link with force
wgmesh disconnect pipe250 force
```

## Clean

Removes all dead links that don't ping<br>
Be careful, you could remove links to a server that just has an outage.
```
wgmesh clean
```

## Shutdown/Startup

You can shutdown all links with
```
wgmesh down
```
Or start them all up
```
wgmesh up && systemctl restart wgmesh
```

## Enable / Disable

To enable/disable settings<br>
To view all possible commands just run enable or disable without any parameters

```
wgmesh enable/disable ospfv3
```

## Set

To set specific settings such as defaultLinkType<br>
To view all possible commands just run set without any parameters

```
wgmesh set defaultLinkType wgobfs
```

## Used

Prints out the used id's
```
wgmesh used
```

## Bender

Prints out a config for the route bender 4000
```
wgmesh bender
```

## Proximity

Prints out nodes sorted by latency
```
wgmesh proximity
```

Proxmity can also cutoff based on latency
```
wgmesh proximity 200
```

## Migrate

Will migrate any config changes
```
wgmesh migrate
```

## Recover

In case your bird config is fucked beyond repair.<br>
Don't forget to restart bird after this.
```
wgmesh recover
```

## Token

Prints out the tokens, you can also find them in logs/ or in the tokens.json file
```
wgmesh token
```

## Cost

You can increase a link cost manually by hand

```
wgmesh cost pipe5 5000
```