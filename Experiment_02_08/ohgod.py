#!/usr/bin/env python3
import os
import time
import argparse
import sys
import subprocess
import signal
import threading

# ================= CONFIGURATION =================
APP_NAME = "miniMD_openmpi"
# LOOP_SLEEP_SEC = 0.5
LOOP_SLEEP_SEC = 1.0
# Freq Thresholds
# UTIL_LOW_LIMIT = 33.0
# UTIL_HIGH_LIMIT = 66.0
UTIL_LOW_LIMIT = 15
UTIL_HIGH_LIMIT = 40
CPU_ACTIVE_THRESHOLD = 6

# Freq Values (Update these for your specific CPU!)
FREQ_MAX = 2000000
FREQ_MID = 1600000
FREQ_MIN = 1200000

# ================= 0. INSTANT STOP SIGNAL =================
stop_event = threading.Event()

def signal_handler(signum, frame):
    stop_event.set()

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# ================= 1. WATCHDOG =================
def get_target_pids():
    try:
        # Check for the app (low overhead subprocess)
        out = subprocess.check_output(
            ["pgrep", "-u", os.environ.get("USER"), "-f", APP_NAME],
            text=True
        ).strip()
        if out:
            return [int(x) for x in out.split() if x.isdigit()]
    except:
        pass
    return []

def are_pids_alive(pids):
    for pid in pids:
        try:
            # Signal 0 checks existence without killing
            os.kill(pid, 0)
            return True
        except OSError:
            pass
    return False

# ================= 2. CORE MONITOR =================
class CoreUtilMonitor:
    def __init__(self, monitored_cores):
        self.cores = set(monitored_cores)
        self.prev_totals = {}
        self.prev_idles = {}
        try:
            self.f = open("/proc/stat", "r")
        except Exception as e:
            sys.exit(f"[ERROR] /proc/stat: {e}")

    def get_utilization(self):
        self.f.seek(0)
        results = {}
        for line in self.f:
            if not line.startswith("cpu"): continue
            parts = line.split()
            if len(parts[0]) == 3: continue

            core_id = int(parts[0][3:])
            if core_id not in self.cores: continue

            idle = int(parts[4]) + int(parts[5])
            total = sum(int(x) for x in parts[1:])

            if core_id in self.prev_totals:
                d_total = total - self.prev_totals[core_id]
                d_idle = idle - self.prev_idles[core_id]
                results[core_id] = (1.0 - (d_idle / d_total)) * 100.0 if d_total > 0 else 0.0

            self.prev_totals[core_id] = total
            self.prev_idles[core_id] = idle
        return results

    def close(self):
        if self.f: self.f.close()

# ================= 3. CONTROLLER =================
class DirectFrequencyController:
    def __init__(self, allowed_cores, monitor_only=False):
        self.handles = {}
        self.last_freq = {}
        self.monitor_only = monitor_only

        if not monitor_only:
            # Force Userspace Governor
            for c in allowed_cores:
                try:
                    with open(f"/sys/devices/system/cpu/cpu{c}/cpufreq/scaling_governor", 'w') as f:
                        f.write("userspace")
                    self.handles[c] = open(f"/sys/devices/system/cpu/cpu{c}/cpufreq/scaling_setspeed", 'w')
                    self.last_freq[c] = 0
                except: pass

    def set_freq(self, core, freq):
        if self.monitor_only: return
        if core in self.handles and self.last_freq.get(core) != freq:
            try:
                f = self.handles[core]
                f.seek(0)
                f.write(str(freq))
                f.flush()
                self.last_freq[core] = freq
            except: pass

    def close(self):
        for h in self.handles.values(): h.close()

# ================= 4. MAIN LOOP =================
def run_monitor(cores, heartbeat=False, monitor_only=False):
    # === ADDED: Print exactly which cores Python is watching ===
    print(f"[PYTHON] Monitoring Worker Cores: {sorted(list(cores))}")
    sys.stdout.flush()
    # ===========================================================

    util_monitor = CoreUtilMonitor(cores)
    controller = DirectFrequencyController(cores, monitor_only=monitor_only)

    # Wait for App (Check every 0.1s)
    target_pids = []
    while not target_pids and not stop_event.is_set():
        target_pids = get_target_pids()
        if not target_pids:
            stop_event.wait(0.1)

    # Monitor Loop
    try:
        util_monitor.get_utilization() # Prime
        while not stop_event.is_set():
            if not are_pids_alive(target_pids): break

            # Wait 0.5s OR stop immediately if signal received
            if stop_event.wait(LOOP_SLEEP_SEC): break

            util_data = util_monitor.get_utilization()

            # Logic & Control
            counts = {"LOW":0, "MID":0, "HIGH":0}
            total_u = 0

            for c, u in util_data.items():
                if u <= CPU_ACTIVE_THRESHOLD: f, b = FREQ_MID, "LOW"
                else: f, b = FREQ_MAX, "HIGH"

                controller.set_freq(c, f)
                counts[b]+=1
                total_u += u

            if heartbeat:
                avg = total_u / len(util_data) if util_data else 0
                print(f"Avg: {avg:.1f}% | {counts}")

    finally:
        util_monitor.close()
        controller.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--cores', type=str, default="0-30")
    parser.add_argument('--heartbeat', action='store_true')
    parser.add_argument('--monitor-only', action='store_true')
    args = parser.parse_args()

    # Parse core list "0-7,9"
    cores = []
    for part in args.cores.split(','):
        if '-' in part:
            s, e = map(int, part.split('-'))
            cores.extend(range(s, e+1))
        else:
            cores.append(int(part))

    run_monitor(cores, heartbeat=args.heartbeat, monitor_only=args.monitor_only)