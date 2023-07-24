import sys
sys.path.append("..") # Adds higher directory to python modules path.

from Class.base import Base
B = Base()

for i in range(1,100):
    print("Updating",f"10.0.{i}.1")
    resp = B.cmd(f"""ssh root@10.0.{i}.1 <<EOF
su wg-mesh
cd
timeout 10 git pull --ff-only
exit
systemctl restart wgmesh
systemctl restart wgmesh-bird
EOF""",10)
    print(resp)

print("END")
