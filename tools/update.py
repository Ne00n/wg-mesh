import socket, sys
sys.path.append("..") # Adds higher directory to python modules path.

from Class.base import Base
B = Base()

for i in range(1,250):
    #check if SSH is reachable
    print("Checking,"f"10.0.{i}.1")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    try: s.connect((f"10.0.{i}.1", 22)) 
    except: continue 
    #continue
    print("Updating",f"10.0.{i}.1")
    resp = B.cmd(f"""ssh root@10.0.{i}.1 <<EOF
su wg-mesh
cd
timeout 10 git pull --ff-only
python3 cli.py migrate
exit
systemctl restart wgmesh
systemctl restart wgmesh-bird
systemctl restart wgmesh-rotate
EOF""",60)
    print(resp)

print("END")
