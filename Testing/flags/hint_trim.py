#!/usr/bin/env python3
"""
INTELLIGENT CAPSTONE CONTROLLER - Version 27.0 (Final)
1. COMPUTE/COMM -> MAX (2.0 GHz)
2. MEMORY_BOUND -> MED (1.6 GHz) [Triggered only if Data > L3 Cache]
3. IO_STORAGE   -> MIN (1.2 GHz)
4. CORE PARKING -> Active=Target, Passive=MIN
"""
import sys
import time
import os
import glob
import subprocess

# ---------------------- CONFIGURATION ----------------------
HINT_FILE = "/dev/shm/minimd_phase_hint"
POLL_INTERVAL = 0.001  # 1ms polling

# ---------------------- HARDWARE CONTROL ----------------------
class FrequencyGovernor:
    def __init__(self):
        self.cpu_files = []
        self.num_cores = 0
        self.available_freqs = []
        
        # 1. DETECT CORES
        gov_files = glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor")
        self.num_cores = len(gov_files)
        
        # 2. DETECT FREQUENCIES
        try:
            with open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_frequencies", "r") as f:
                self.available_freqs = sorted([int(x) for x in f.read().strip().split()], reverse=True)
        except:
            self.available_freqs = [2400000, 1600000, 1200000]

        self.FREQ_MAX = self.available_freqs[0]   # 2.4 GHz
        self.FREQ_MED = self.available_freqs[len(self.available_freqs)//2] # 1.6 GHz
        self.FREQ_MIN = self.available_freqs[-1]  # 1.2 GHz

        print(f"[GOVERNOR] MAX: {self.FREQ_MAX}, MED: {self.FREQ_MED}, MIN: {self.FREQ_MIN}")

        # 3. SETUP HANDLES
        for i in range(self.num_cores):
            path_set = f"/sys/devices/system/cpu/cpu{i}/cpufreq/scaling_setspeed"
            try:
                try: 
                    with open(f"/sys/devices/system/cpu/cpu{i}/cpufreq/scaling_governor", 'w') as f: f.write("userspace")
                except: pass
                
                f = open(path_set, 'w')
                self.cpu_files.append(f)
            except:
                self.cpu_files.append(None)

    def apply_strategy(self, strategy, active_cores):
        # STRATEGY MAPPING
        if strategy == "PERFORMANCE": target = self.FREQ_MAX
        elif strategy == "MEMORY":    target = self.FREQ_MED  # <-- THIS WAS MISSING
        elif strategy == "POWERSAVE": target = self.FREQ_MIN
        
        for i, f_handle in enumerate(self.cpu_files):
            if f_handle is None: continue
            
            # CORE PARKING LOGIC
            if i in active_cores:
                val = target
            else:
                val = self.FREQ_MIN # Park unused cores

            try:
                f_handle.seek(0)
                f_handle.write(str(val))
                f_handle.flush()
            except OSError: pass

# ---------------------- HELPER: FIND ACTIVE CORES ----------------------
def get_active_cores():
    active = set()
    try:
        r = subprocess.run(["pgrep", "miniMD_openmpi"], capture_output=True, text=True)
        pids = r.stdout.strip().split()
        if not pids: return set()

        for pid in pids:
            try:
                with open(f"/proc/{pid}/stat", 'r') as f:
                    content = f.read()
                    fields = content.split()
                    if len(fields) > 38:
                        core_id = int(fields[38])
                        active.add(core_id)
            except: pass
    except: pass
    return active

# ---------------------- MAIN LOOP ----------------------
def run_controller():
    print(f"[INFO] V27 Final Controller. Polling {HINT_FILE}")
    
    gov = FrequencyGovernor()
    last_phase = "UNKNOWN"
    active_cores = set()
    
    # 1. Wait for miniMD
    print("[INIT] Waiting for miniMD processes...")
    while not active_cores:
        active_cores = get_active_cores()
        time.sleep(0.5)
    
    print(f"[INIT] Detected Active Cores: {sorted(list(active_cores))}")
    print(f"[INIT] Parking all other cores to {gov.FREQ_MIN} Hz")

    # 2. Wait for Hint File
    while not os.path.exists(HINT_FILE):
        time.sleep(0.1)

    # 3. Control Loop
    try:
        with open(HINT_FILE, "r") as f:
            while True:
                f.seek(0)
                phase = f.read().strip()
                
                if phase and phase != last_phase:
                    
                    if phase == "IO_STORAGE":
                        # DISK BOUND: SAFE TO THROTTLE
                        gov.apply_strategy("POWERSAVE", active_cores)
                        
                    elif phase == "MEMORY_BOUND":
                        # MEMORY BOUND (Verified by C++ Heuristic): SAFE TO THROTTLE
                        gov.apply_strategy("MEMORY", active_cores)
                        
                    else:
                        # COMPUTE, COMMUNICATION, SERIAL -> MAX
                        gov.apply_strategy("PERFORMANCE", active_cores)
                    
                    last_phase = phase
                
                time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print("\n[INFO] Stopping.")

if __name__ == "__main__":
    run_controller()