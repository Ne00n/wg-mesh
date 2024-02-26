import sys
sys.path.append("..") # Adds higher directory to python modules path.

from Class.base import Base
B = Base()

for i in range(1,100):
    print("Cleaning",f"10.0.{i}.1")
    resp = B.cmd(f"""ssh root@10.0.{i}.1 <<EOF
/opt/wg-mesh/cli.py clean
EOF""",120)
    print(resp)

print("END")
