# Cron

## bird

Responsible for generating the bird config and watching for any config changes to rebuild that config.<br>
Also keeps an eye on links if they die, have packet loss

Associated systemd service: wgmesh-bird

## rotate

If ipt_xor is used, the cronjob is used, to swap the keys a few times per day.<br>
It increases the link cost at first, to offload any traffic before the link is shutdown and reconfigured.

Includes systemd support, to avoid the process getting killed while swapping out the keys.<br>
Associated systemd service: wgmesh-rotate

## smoke

Used to generate a smokeping file, so you don't have to do that by hand.<br>
Should be run as root.