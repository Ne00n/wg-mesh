# Folders

## Class

Contains all class files for wg-mesh

## configs

Contains the main config file plus some systemd template files and an nginx example file for the reverse proxy

## cron

Contains the cronjobs, see cron.md

## docs

Well yea

## links

Oh boy, basically it has all the configuration files for the links.<br>
Including private keys, preshared keys, also the bash files for each link, which you can toggle individually.

Like this, to bring the link up.
```
bash pipe5.sh up
```

Or to shut it down.
```
bash pipe5.sh
```

You can also modify these, they won't be overwritten as long you don't use /update api call, which can update the port and other stuff.

## logs

Well see logs.md

## tools

Contains some useful tools, such as install scripts for ipt_xor, wgobfs and amneziawg.<br>
Additionally, you find an update script, that just runs through the network and updates the wg-mesh version on all nodes.

Clean basically does the same just cleans up dead links on all nodes, same for machine-id which flags up duplicate mac addresses, see throubleshooting.md.<br>
Patch does modify the bird systemd file to give it a higher priority, you can apply it, you don't have to, it does noticably at least on smokeping reduce the internal latency by a fraction of a millisecond.<br>
Status just prints out the status of the wgmesh-bird deamon.