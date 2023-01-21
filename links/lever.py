#!/usr/bin/python3
import subprocess, sys, os
#load files
path = os.path.dirname(os.path.realpath(__file__))
files = os.listdir(f'{path}')
for file in list(files):
    if not file.endswith(".sh"): files.remove(file)
if len(sys.argv) == 1:
    exit("Missing parameter")
elif sys.argv[1] == "up" or sys.argv[1] == "down":
    for file in files:
        subprocess.run(f"bash {path}/{file} {sys.argv[1]}",shell=True)
else:
    exit("Unknown parameter")