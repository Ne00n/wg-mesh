import multiprocessing as mp, systemd.daemon, hashlib, random, signal, json, time, os, sys
sys.path.append("..") # Adds higher directory to python modules path.
from Class.base import Base

refresh, shutdown, = 0, False

def gracefulExit(signal_number,stack_frame):
    global shutdown
    systemd.daemon.notify('STOPPING=1')
    shutdown = True

def initWorker(subnets):
    global sharedSubnets
    sharedSubnets = subnets

def sliceWorker(index):
    global sharedSubnets
    try:
        data = sharedSubnets[index]
        #print(f"Processing {data['subnet']} on index {index}")
        workerTools = Base()
        return workerTools.processSubnet(data)
    except Exception as e:
        print(f"Error processing subnet {data['subnet']} on index {index}: {e}")
        return {}

path = os.path.dirname(os.path.realpath(__file__))
path = path.replace("/cron","")

config = {"dataSrc": "https://routing.serv.app","cutOff":10,"asnList": {"32590":{}}}
if not os.path.isfile(f"{path}/configs/asn.json"):
    with open(f"{path}/configs/asn.json", 'w') as f: json.dump(config, f)
else:
    with open(f"{path}/configs/asn.json") as handle: config =  json.loads(handle.read())
tools = Base()

signal.signal(signal.SIGINT, gracefulExit)
signal.signal(signal.SIGTERM, gracefulExit)
systemd.daemon.notify('READY=1')

waitUntil = 0
while True:
    if shutdown:
        print("Shutting down gracefully...")
        exit(0)

    currentTime = int(time.time())
    if currentTime < waitUntil: 
        time.sleep(2)
        continue
    waitUntil = currentTime + random.randint(1800,3600)

    print("Updating local asn's")
    for asn, settings in config['asnList'].items():
        print(f"Loading {asn}.json")
        success, req = tools.call(url=f"{config['dataSrc']}/seeds/{asn}.json",method="GET")
        if not success: continue
        pingable = req.json()
        asnFile = {}
        if not os.path.isfile(f"{path}/data/{asn}.json"):
            for subnet in pingable:
                if not subnet in asnFile: asnFile[subnet] = {"created":int(time.time()),"updated":0,"settings":"","data":{}}
            with open(f"{path}/data/{asn}.json", 'w') as f: json.dump(asnFile, f)
        else:
            try:
                with open(f"{path}/data/{asn}.json") as handle: asnFile =  json.loads(handle.read())
            except Exception as e:
                print(f"Error, failed to load {asn}: {e}")
                if os.path.isfile(f"{path}/data/{asn}.json"): os.remove(f"{path}/data/{asn}.json")
                continue
            for subnet in pingable:
                if not subnet in asnFile:
                    print(f"Adding {subnet} to {asn}")
                    asnFile[subnet] = {"created":int(time.time()),"updated":0,"settings":"","data":{}}
            for subnet in list(asnFile):
                if not subnet in list(pingable):
                    print(f"Deleting {subnet} from {asn}")
                    del asnFile[subnet]
            with open(f"{path}/data/{asn}.json", 'w') as f: json.dump(asnFile, f)

    subnets, mapping = [], {}
    print("Processing local asn's")
    files = os.listdir(f"{path}/data/")
    for file in files:
        if not file.endswith(".json"): continue
        print(f"Loading {file}")
        with open(f"{path}/data/{file}") as handle: asnData =  json.loads(handle.read())
        success, req = tools.call(url=f"{config['dataSrc']}/seeds/{file}",method="GET")
        if not success: continue
        pingable = req.json()
        for prefix, details in asnData.items():
            #ignore ipv6 for now
            if "::" in prefix: continue
            if details['updated'] > int(time.time()): continue
            tmpSubnets = tools.splitTo24(prefix)
            for subnet in tmpSubnets: 
                if not subnet in pingable: 
                    #print(f"Skipping {subnet}, not pingable")
                    continue
                subnets.append({"subnet":subnet,"details":details,"pingable":pingable[subnet]})
            #print(f"{prefix} splitted into {len(tmpSubnets)} subnet(s)")
            for subnet in tmpSubnets: 
                mapping[subnet] = {"file":file,"prefix":prefix}
        print(f"Loaded {file}")
        #do one file at a time
        if subnets: break

    print(f"Running {file} with {len(subnets)} subnets")
    if os.path.exists(f"{path}/results.jsonl"): os.remove(f"{path}/results.jsonl")
    pool = mp.Pool(processes=4, initializer=initWorker, initargs=(subnets,), maxtasksperchild=1000)
    try:
        with open(f"{path}/results.jsonl", 'a') as writer:
            for result in pool.imap_unordered(sliceWorker, range(len(subnets)), chunksize=1):
                if result is not None: writer.write(json.dumps(result) + '\n')
    finally:
        pool.close()
        pool.join()
        pool.terminate()

    toWrite, subnets = {}, {}
    with open(f"{path}/results.jsonl", 'r') as results:
        for line in results:
            row = json.loads(line)
            for subnet,pings in row.items():
                info = mapping[subnet]
                if not info['file'] in toWrite: toWrite[info['file']] = {}
                if not info['prefix'] in toWrite[info['file']]: toWrite[info['file']][info['prefix']] = []
                toWrite[info['file']][info['prefix']].append((subnet,pings))
    
    mapping = []
    if os.path.exists(f"{path}/results.jsonl"): os.remove(f"{path}/results.jsonl")

    for file, data in toWrite.items():
        print(f"Writing file {file}")
        with open(f"{path}/data/{file}") as handle: asnData =  json.loads(handle.read())
        for prefix, subnets in data.items():
            days, hours = random.randint(6, 7), random.randint(22,24)
            asnData[prefix]['updated'] = int(time.time()) + (60*60*hours*days)
            if not "subnets" in asnData[prefix]: asnData[prefix]['data'] = {}
            for row in subnets:
                if not subnet in asnData[prefix]['data']: asnData[prefix]['data'][row[0]] = []
                asnData[prefix]['data'][row[0]] += row[1]
        with open(f"{path}/data/{file}", 'w') as f: json.dump(asnData, f)
    
    print("Generating static routes")
    gateway = tools.cmd("ip route show default | awk '/default via / {print $3; exit}' | tr -d '\n'")[0]
    rules = ""
    for file in files:
        if not file.endswith(".json"): continue
        print(f"Loading {file}")
        with open(f"{path}/data/{file}") as handle: pingable =  json.loads(handle.read())
        for prefix, rows in pingable.items():
            for subnet, latency in rows['data'].items():
                if latency and latency[0][1] < config['cutOff']:
                    rules += f'route {subnet} via {gateway};\n'
    tools.saveFile(rules,"/etc/bird/static.conf")

    toWrite = {}
    print(f"Loop done")
    time.sleep(2)