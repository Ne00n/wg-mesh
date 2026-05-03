import multiprocessing as mp, systemd.daemon, ipaddress, hashlib, logging, random, signal, json, time, os, sys
from logging.handlers import RotatingFileHandler
sys.path.append("..") # Adds higher directory to python modules path.
from Class.base import Base

shutdown = False
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

tools = Base()
path = os.path.dirname(os.path.realpath(__file__))
path = path.replace("/cron","")

#logging
level = "info"
levels = {'critical': logging.CRITICAL,'error': logging.ERROR,'warning': logging.WARNING,'info': logging.INFO,'debug': logging.DEBUG}
stream_handler = logging.StreamHandler()
stream_handler.setLevel(levels[level])
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',datefmt='%d.%m.%Y %H:%M:%S',level=levels[level],handlers=[RotatingFileHandler(maxBytes=10000000,backupCount=5,filename=f"{path}/logs/routing.log"),stream_handler])
logger = logging.getLogger()

gateway = tools.cmd("ip route show default | awk '/default via / {print $3; exit}' | tr -d '\n'")[0]
asnConfig = {"dataSrc": "https://routing.serv.app","batchSize":5000,"cutOff":5,"asnList": {"32590":{}}}
if not os.path.isfile(f"{path}/configs/asn.json"):
    with open(f"{path}/configs/asn.json", 'w') as f: json.dump(asnConfig, f, indent=4)
else:
    with open(f"{path}/configs/asn.json") as handle: asnConfig =  json.loads(handle.read())

signal.signal(signal.SIGINT, gracefulExit)
signal.signal(signal.SIGTERM, gracefulExit)
systemd.daemon.notify('READY=1')

waitUntil = 0
while True:
    if shutdown:
        logger.info("Stopping")
        exit(0)

    currentTime = int(time.time())
    if currentTime < waitUntil: 
        time.sleep(2)
        continue
    waitUntil = currentTime + random.randint(1800,3600)

    logger.info("Updating local asn's")
    for asn, settings in asnConfig['asnList'].items():
        logger.debug(f"Loading {asn}.json")
        success, req = tools.call(url=f"{asnConfig['dataSrc']}/seeds/{asn}.json",method="GET")
        if not success: continue
        pingable = req.json()
        if not pingable: continue
        asnFile = {}
        if not os.path.isfile(f"{path}/data/{asn}.json"):
            for subnet in pingable:
                if not subnet in asnFile: asnFile[subnet] = {"created":int(time.time()),"updated":0,"settings":"","subnets":{}}
            with open(f"{path}/data/{asn}.json", 'w') as f: json.dump(asnFile, f)
        else:
            try:
                with open(f"{path}/data/{asn}.json") as handle: asnFile =  json.loads(handle.read())
            except Exception as e:
                logger.info(f"Error, failed to load {asn}: {e}")
                if os.path.isfile(f"{path}/data/{asn}.json"): os.remove(f"{path}/data/{asn}.json")
                continue
            added = 0
            for subnet in pingable:
                if not subnet in asnFile:
                    logger.debug(f"Adding {subnet} to {asn}")
                    added += 1
                    asnFile[subnet] = {"created":int(time.time()),"updated":0,"settings":"","subnets":{}}
            if added: logger.info(f"Added {added} subnets to AS{asn}")
            deleted = 0
            for subnet in list(asnFile):
                if not subnet in list(pingable):
                    deleted += 1
                    logger.debug(f"Deleting {subnet} from {asn}")
                    del asnFile[subnet]
            if deleted: logger.info(f"Deleted {deleted} subnets from AS{asn}")
            with open(f"{path}/data/{asn}.json", 'w') as f: json.dump(asnFile, f)

    subnets, mapping, asnFile = [], {}, {}
    logger.info("Processing local asn's")
    files = os.listdir(f"{path}/data/")
    random.shuffle(files)
    for file in files:
        if not file.endswith(".json"): continue
        logger.debug(f"Loading {file}")
        with open(f"{path}/data/{file}") as handle: asnData =  json.loads(handle.read())
        success, req = tools.call(url=f"{asnConfig['dataSrc']}/seeds/{file}",method="GET")
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
            #to reduce memory usage, we break after 10k
            if len(subnets) > asnConfig['batchSize']: break
        #do one file at a time
        if subnets: 
            #skip wait until subnets is empty
            waitUntil = 0
            break

    logger.info(f"Running {file} with {len(subnets)} subnets")
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
        logger.info(f"Writing file {file}")
        with open(f"{path}/data/{file}") as handle: asnData =  json.loads(handle.read())
        for prefix, subnets in data.items():
            days, hours = random.randint(2, 4), random.randint(22,24)
            asnData[prefix]['updated'] = int(time.time()) + (60*60*hours*days)
            if not "subnets" in asnData[prefix]: asnData[prefix]['subnets'] = {}
            for row in subnets:
                if not row[0] in asnData[prefix]['subnets']: asnData[prefix]['subnets'][row[0]] = []
                avrg = tools.getAvrg(row[1])
                asnData[prefix]['subnets'][row[0]].append(int(avrg))
                asnData[prefix]['subnets'][row[0]][-5:]
        with open(f"{path}/data/{file}", 'w') as f: json.dump(asnData, f)
    
    logger.info("Generating static routes")
    rules, toWrite = "", {}
    for asn in asnConfig['asnList']:
        if not os.path.isfile(f"{path}/data/{asn}.json"): continue
        logger.debug(f"Loading {asn}")
        with open(f"{path}/data/{asn}.json") as handle: pingable =  json.loads(handle.read())
        toAggregate = []
        for prefix, rows in pingable.items():
            if not "subnets" in rows:
                logger.warning(f"Missing subnets for {prefix} in {asn}.json")
                continue
            for subnet, latency in rows['subnets'].items():
                if not latency:
                    logger.warning(f"Missing latency for {subnet} in {asn}.json")
                    continue
                avrg = tools.getAvrg(latency)
                if avrg < asnConfig['cutOff']: toAggregate.append(ipaddress.ip_network(subnet))
        aggregated = tools.aggregate(toAggregate)
        for subnet in aggregated:
            rules += f'route {subnet} via {gateway};\n'

    pingable = {}
    tools.saveFile(rules,"/etc/bird/static.conf")
    logger.debug("Reloading asn.json")
    try:
        with open(f"{path}/configs/asn.json") as handle: asnConfig =  json.loads(handle.read())
    except:
        logger.warning(f"Failed to reload asn.json")

    logger.info(f"Loop done")
    time.sleep(2)