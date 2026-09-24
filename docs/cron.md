# Cron

## bird

Responsible for generating the bird config and watching for any config changes to rebuild that config.<br>
Also keeps an eye on links if they die, have packet loss

Associated systemd service: wgmesh-bird

## smoke

Used to generate a smokeping file, so you don't have to do that by hand.<br>
Should be run as root.