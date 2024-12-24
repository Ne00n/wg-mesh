import sys
sys.path.append("..") # Adds higher directory to python modules path.

from Class.base import Base
B = Base()

for i in range(0,250):
    print("Updating",f"10.0.{i}.1")
    resp = B.cmd(f"""ssh root@10.0.{i}.1 <<EOF1
SYSTEMD_EDITOR=tee systemctl edit --full bird <<'EOF2'
# /lib/systemd/system/bird.service
[Unit]
Description=BIRD Internet Routing Daemon
After=network.target

[Service]
EnvironmentFile=/etc/bird/envvars
ExecStartPre=/usr/lib/bird/prepare-environment
ExecStartPre=/usr/sbin/bird -p
ExecReload=/usr/sbin/birdc configure
ExecStart=/usr/sbin/bird -f -u $BIRD_RUN_USER -g $BIRD_RUN_GROUP $BIRD_ARGS
Restart=on-abort
CPUSchedulingPolicy=fifo
CPUSchedulingPriority=40

[Install]
WantedBy=multi-user.target
EOF2
systemctl restart bird
systemctl enable bird
EOF1""",30)
    print(resp)

print("END")
