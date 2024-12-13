import socket, sys
sys.path.append("..") # Adds higher directory to python modules path.

from Class.base import Base
B = Base()

for i in range(0,250):
    #check if SSH is reachable
    print("Checking,"f"10.0.{i}.1")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    try: s.connect((f"10.0.{i}.1", 22)) 
    except: continue 
    #continue
    print("Cleaning",f"10.0.{i}.1")
    resp = B.cmd(f"""ssh root@10.0.{i}.1 <<EOF
/opt/wg-mesh/cli.py clean
EOF""",120)
    for line in resp: print(line)

print("END")
