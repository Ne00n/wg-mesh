import sys
sys.path.append("..") # Adds higher directory to python modules path.

from Class.base import Base
B = Base()

ids = {}
for i in range(0,200):
    print(f"10.0.{i}.1","Checking machine-ID")
    resp = B.cmd(f"ssh root@10.0.{i}.1 cat /etc/machine-id",3)
    if resp[0] == "": continue
    print(f"Got {resp[0].rstrip()}")
    ids[i] = resp[0]

currentIDs = []
for id,machineID in ids.items():
    if machineID in currentIDs:
        for id,collisionID in ids.items():
            if collisionID and collisionID == machineID:
                print(id,collisionID.rstrip())
    currentIDs.append(machineID)
print("END")
