import socket, sys
sys.path.append("..") # Adds higher directory to python modules path.

from Class.base import Base
B = Base()

for i in range(1,250):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    try: s.connect((f"10.0.{i}.1", 22)) 
    except: continue 
    resp = B.cmd(f"""ssh root@10.0.{i}.1 <<EOF
systemctl status wgmesh-bird
EOF""",10)
    if "Active: active (running)" in resp[0]:
        print(f"10.0.{i}.1 OK")
    else:
        print(f"10.0.{i}.1 FAIL")

print("END")
