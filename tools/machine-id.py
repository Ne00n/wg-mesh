import sys
sys.path.append("..") # Adds higher directory to python modules path.

from Class.base import Base
B = Base()

ids = {}
for i in range(1,50):
    print(i,"Checking machine-ID")
    resp = B.cmd(f"ssh root@10.0.{i}.1 cat /etc/machine-id")
    if resp[0] == "": continue
    ids[i] = resp[0]

currentIDs = []
for id,machineID in ids.items():
    if machineID in currentIDs:
        print(f"Found collision")
        for id,collisionID in ids.items():
            if collisionID == machineID:
                print(id,collisionID)
    currentIDs.append(machineID)
print("END")