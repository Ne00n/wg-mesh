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
config = tools.readFile(f'{path}/configs/config.json')
asnConfig = {"dataSrc": "https://routing.serv.app","batchSize":5000,"cutOff":5,"asnList": {"32590":{}}}
if not os.path.isfile(f"{path}/configs/asn.json"):
    with open(f"{path}/configs/asn.json", 'w') as f: json.dump(asnConfig, f, indent=4)
else:
    asnConfig = tools.readFile(f'{path}/configs/asn.json')

signal.signal(signal.SIGINT, gracefulExit)
signal.signal(signal.SIGTERM, gracefulExit)
systemd.daemon.notify('READY=1')

waitUntil, reloadUntil, updated = 0, 0, {}
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
        if not asn in updated: updated[asn] = 0
        if updated[asn] > int(time.time()): continue
        logger.debug(f"Loading {asn}.json")
        success, req = tools.call(url=f"{asnConfig['dataSrc']}/seeds/{asn}.json",method="GET")
        if not success: continue
        pingable = req.json()
        if not pingable: continue
        asnFile = {}
        if not os.path.isfile(f"{path}/data/{asn}.json"):
            for prefix in pingable:
                if not prefix in asnFile: asnFile[prefix] = {"created":int(time.time()),"updated":0,"settings":"","subnets":{}}
            with open(f"{path}/data/{asn}.json", 'w') as f: json.dump(asnFile, f)
        else:
            try:
                with open(f"{path}/data/{asn}.json") as handle: asnFile =  json.loads(handle.read())
            except Exception as e:
                logger.info(f"Error, failed to load {asn}: {e}")
                if os.path.isfile(f"{path}/data/{asn}.json"): os.remove(f"{path}/data/{asn}.json")
                continue
            added = 0
            for prefix in pingable:
                if not prefix in asnFile:
                    logger.debug(f"Adding {prefix} to {asn}")
                    added += 1
                    asnFile[prefix] = {"created":int(time.time()),"updated":0,"settings":"","subnets":{}}
            if added: logger.info(f"Added {added} subnets to AS{asn}")
            deleted = 0
            for prefix in list(asnFile):
                if not prefix in pingable:
                    deleted += 1
                    logger.debug(f"Deleting {prefix} from {asn}")
                    del asnFile[prefix]
            if deleted: logger.info(f"Deleted {deleted} subnets from AS{asn}")
            with open(f"{path}/data/{asn}.json", 'w') as f: json.dump(asnFile, f)
        #already processed asn files will be on cooldown for 24 hours
        updated[asn] = int(time.time()) + (60*60*24*2)

    subnets, mapping, asnFile, pingable = [], {}, {}, {}
    logger.info("Processing local asn's")
    files = asnConfig['asnList']
    random.shuffle(files)
    for file in files:
        if not os.path.isfile(f"{path}/data/{file}.json"): continue
        logger.debug(f"Loading {file}")
        asnData = tools.readFile(f"{path}/data/{file}.json")
        if not tools.isCached(f"{path}/data/cache/{file}.json"):
            success, req = tools.call(url=f"{asnConfig['dataSrc']}/seeds/{file}",method="GET")
            if not success: continue
            tools.saveFile(f"{path}/data/cache/{file}.json",req.json())
            pingable = req.json()
        else:
            pingable = tools.readFile(f"{path}/data/cache/{file}.json")
        for prefix, details in asnData.items():
            #ignore ipv6 for now
            if "::" in prefix: continue
            if details['updated'] > int(time.time()): continue
            for subnet, octects in pingable[prefix].items():
                subnets.append({"subnet":subnet,"details":details,"pingable":octects})
                #to reduce memory usage, we break after batchSize
                if len(subnets) > asnConfig['batchSize']: break
            for subnet in list(pingable[prefix]): 
                mapping[subnet] = {"file":file,"prefix":prefix}
            #to reduce memory usage, we break after batchSize
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
            days, hours = random.randint(2, 4), random.randint(20,24)
            asnData[prefix]['updated'] = int(time.time()) + (60*60*hours*days)
            if not "subnets" in asnData[prefix]: asnData[prefix]['subnets'] = {}
            for row in subnets:
                if not row[0] in asnData[prefix]['subnets']: asnData[prefix]['subnets'][row[0]] = []
                avrg = tools.getAvrg(row[1])
                asnData[prefix]['subnets'][row[0]].append(int(avrg))
                asnData[prefix]['subnets'][row[0]][-5:]
        with open(f"{path}/data/{file}", 'w') as f: json.dump(asnData, f)
    
    toWrite = {}
    if currentTime > reloadUntil: 
        logger.info("Generating static routes")
        rules = ""
        for asn, details in asnConfig['asnList'].items():
            if not os.path.isfile(f"{path}/data/{asn}.json"): continue
            logger.debug(f"Loading {asn}")
            with open(f"{path}/data/{asn}.json") as handle: pingable =  json.loads(handle.read())
            toAggregate = []
            for prefix, rows in pingable.items():
                if not "subnets" in rows:
                    logger.warning(f"Missing subnets for {prefix} in {asn}.json")
                    continue
                routed, toBeAggregated = 0, []
                for subnet, latency in rows['subnets'].items():
                    if not latency:
                        logger.warning(f"Missing latency for {subnet} in {asn}.json")
                        continue
                    avrg = tools.getAvrg(latency)
                    if "location" in details and str(config['id']) in details['location']:
                        minimum = details['location'][str(config['id'])]['minimum']
                        cutoff = details['location'][str(config['id'])]['cutoff']
                    else:
                        cutoff, minimum = asnConfig['cutOff'], 0
                    if avrg < minimum: continue
                    if avrg < cutoff:
                        toBeAggregated.append(ipaddress.ip_network(subnet))
                        #routed += 1
                if routed == len(rows['subnets']):
                    toAggregate.append(ipaddress.ip_network(prefix))
                else:
                    toAggregate.extend(toBeAggregated)
            aggregated = tools.aggregate(toAggregate)
            for subnet in aggregated:
                rules += f'route {subnet} via {gateway};\n'

        tools.saveFile(rules,"/etc/bird/static.conf")
        reloadUntil = currentTime + random.randint(21600,28800)

    pingable = {}
    logger.debug("Reloading asn.json")
    try:
        asnConfig = tools.readFile(f'{path}/configs/asn.json')
        reloadUntil = 0
    except:
        logger.warning(f"Failed to reload asn.json")

    logger.info(f"Loop done")
    time.sleep(2)