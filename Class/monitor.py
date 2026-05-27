from threading import Thread
from Class.base import Base
import time, re

class Monitor(Base):
    def __init__(self, path, logger):
        self.logger = logger
        super().__init__()
        self.path = path
        self.toMonitor = ["packets"]
        self.thresholdMultiplier = 0.5
        self.stddevMultiplier = 3.0  
        self.minAbsRate = 50.0            
        self.emaAlpha = 0.1                          
        self.consecutiveBreaches = 1       
        self.cooldownSeconds = 60          
        self.ignorePrefixes = ('lo')
        self.mapping = {0:"bytes",1:"packets",2:"errs",3:"drop",4:"fifo",5:"frame",6:"compressed",7:"multicast",
                        8:"bytes",9:"packets",10:"errs",11:"drop",12:"fifo",13:"colls",14:"carrier",15:"compressed"}
        self.config = self.readFile(f'{self.path}/configs/config.json')
        # State: history[iface][dir][key]
        self.history = {}

    def getNetDev(self):
        response = []
        for line in open("/proc/net/dev"):
            if ':' not in line: continue
            line = line.rstrip().split()
            iface = line[0].rstrip(':')
            stats = {"interface": iface, "RX": {}, "TX": {}}
            for i, val in enumerate(line[1:9]):
                stats["RX"][self.mapping[i]] = int(val)
            for i, val in enumerate(line[9:]):
                stats["TX"][self.mapping[i]] = int(val)
            response.append(stats)
        return response

    def run(self, interval):
        interfaces = self.getNetDev()
        current_time = int(time.time())

        for stats in interfaces:
            iface = stats['interface']
            if any(iface.startswith(p) for p in self.ignorePrefixes): continue

            for direction in ["RX", "TX"]:
                for key in self.toMonitor:
                    if key not in stats[direction]: continue
                    current_val = int(stats[direction][key])

                    # Initialize tracking state
                    if iface not in self.history: self.history[iface] = {}
                    if direction not in self.history[iface]: self.history[iface][direction] = {}
                    if key not in self.history[iface][direction]:
                        self.history[iface][direction][key] = {
                            "prevVal": current_val,
                            "rates": [],
                            "ema": 0.0,
                            "breachCount": 0,
                            "lastAlert": 0
                        }

                    state = self.history[iface][direction][key]
                    # Calculate rate (samples/sec)
                    delta = current_val - state["prevVal"]
                    if delta < 0: delta = current_val  # Counter reset safety
                    rate = delta / interval if interval > 0 else 0
                    state["prevVal"] = current_val

                    # Update Exponential Moving Average (baseline)
                    if state["ema"] == 0:
                        state["ema"] = rate
                    else:
                        state["ema"] = self.emaAlpha * rate + (1 - self.emaAlpha) * state["ema"]

                    # Rolling window for volatility (last 60 samples = 5 min)
                    state["rates"].append(rate)
                    if len(state["rates"]) > 60: state["rates"].pop(0)

                    # Need baseline stability before alerting
                    if len(state["rates"]) < 10: continue

                    # Calculate standard deviation
                    avg = sum(state["rates"]) / len(state["rates"])
                    variance = sum((x - avg) ** 2 for x in state["rates"]) / len(state["rates"])
                    stddev = variance ** 0.5

                    # Dynamic threshold: baseline spike + volatility buffer + absolute floor
                    threshold = (state["ema"] * (1 + self.thresholdMultiplier)) + (self.stddevMultiplier * stddev)
                    threshold = max(threshold, self.minAbsRate)

                    # Breach detection with dampening & cooldown
                    if rate > threshold:
                        state["breachCount"] += 1
                        if state["breachCount"] >= self.consecutiveBreaches:
                            if current_time - state["lastAlert"] > self.cooldownSeconds:
                                # Log alarm
                                message = f"[{iface} {direction}] Spike: {rate:.1f} {key}/s (EMA: {state['ema']:.1f}, Threshold: {threshold:.1f})"
                                self.logger.warning(message)
                                # Push Alarm
                                if self.config['notifications']['gotifyMonitor']:
                                    sendMessage = Thread(target=self.notify, args=(self.config['notifications']['gotifyMonitor'],f"Node {self.config['id']} {iface}",message))
                                    sendMessage.start()
                                state["lastAlert"] = current_time
                                state["breachCount"] = 0
                    else:
                        state["breachCount"] = 0
