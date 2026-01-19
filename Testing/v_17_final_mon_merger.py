#!/usr/bin/env python3
"""
INTELLIGENT Communication Phase Monitor for miniMD - Version 17.0
OPTIMIZED for LOW OVERHEAD (<2%) using PERF STREAMING
"""
import sys
import subprocess
import time
import csv
import os
import math
import statistics
import glob
import fcntl
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime
from dataclasses import dataclass
from typing import List
from collections import deque

import numpy as np
import fcntl


# ---------------------- CONFIGURATION ----------------------

CMD = ["mpirun", "--oversubscribe", "-np", "32", "./miniMD_openmpi", "i", "in.lj.miniMD"]
LOG_FILE = f"comm_phase_monitor_log.csv"
SUMMARY_FILE = f"comm_phase_summary_log.txt"

# Sample interval
SAMPLE_INTERVAL = 0.2

PERF = "/cvmfs/soft.computecanada.ca/gentoo/2023/x86-64-v3/usr/bin/perf"
RAPL_PATH = "/sys/class/powercap/intel-rapl:0/energy_uj"
RAPL_DRAM_PATH = "/sys/class/powercap/intel-rapl:0:0/energy_uj"

FREQ_MAX = "2000000"
FREQ_MIN = "1600000"

MBPS_CONVERSION_FACTOR = 1048576.0

# Thresholds
IPC_THRESHOLD = 1.6
MISS_THRESHOLD = 0.30
POWER_MARGIN_THRESHOLD = 1.5
TICKS_PER_SECOND = 100
THREAD_APP_LIMIT = 0.25
MAX_CTX_RATE = 1e6



# Network interface to monitor
NETWORK_INTERFACES = ["ib0", "ib1", "eth0", "eth1", "eno1", "ens1"]

EMPIRICAL_SCALING_DATA = {
    2: {"comm_pct": 23.7, "compute_pct": 62.5, "force_pct": 62.5, "neigh_pct": 12.6},
    4: {"comm_pct": 40.2, "compute_pct": 47.5, "force_pct": 47.5, "neigh_pct": 11.7},
    8: {"comm_pct": 75.5, "compute_pct": 14.9, "force_pct": 14.9, "neigh_pct": 9.3},
    16: {"comm_pct": 87.5, "compute_pct": 4.6, "force_pct": 4.6, "neigh_pct": 7.7},
    32: {"comm_pct": 96.9, "compute_pct": 1.9, "force_pct": 1.9, "neigh_pct": 0.3},
    64: {"comm_pct": 97.8, "compute_pct": 0.8, "force_pct": 0.8, "neigh_pct": 0.2}
}

# System metric data object 
@dataclass
class SystemMetrics:
    timestamp: float

    # CPU / Perf
    ipc: float
    miss_rate: float
    cache_ref: float
    cache_miss: float
    cpu_util_all: List[float]   # [user, system, idle, iowait]
    cpu_total_util: float
    iowait_pct: float

    # Power
    pkg_power: float
    dram_power: float

    # Network
    net_rx_mbps: float
    net_tx_mbps: float

    # IO

    # Process Context
    active_ranks: int
    ctx_switches: float
    sync_variance: float

    # Derived/Normalized
    power_per_rank: float = 0.0
    cpu_per_rank: float = 0.0
    effective_cpu_util: float = 0.0


class MetricsCollector:
    def __init__(self, config):
        self.config = config

        # Persitent file handles for minimal sys call overhead
        self.files = {
            'stat': open("/proc/stat", 'r'),
            'net': open("/proc/net/dev", 'r'),
            'rapl': open(config['rapl_path'], 'r') if os.path.exists(config['rapl_path']) else None
        }

        if config.get('dram_path') and os.path.exists(config['dram_path']):
            self.files['dram'] = open(config['dram_path'], 'r')

        self.proc_handles = {}
        
        # state tracking for deltas in calculations
        self.prev = {
            'time': time.time(),
            'pkg_e': 0,
            'dram_e': 0,
            'net_r': 0,  
            'net_s': 0, 
            'ctx': 0, 
            'cpu': [0]*8, #[user time, nice (low prioroity), system time, idle time , iowait, hard interupt time, soft interupt time ]
            'per_proc_cpu': {}
        }

        # perf streaming
        self.perf_process = None
        self.perf_data = {'ipc': 0.0, 'miss': 0.0}

    def start_perf_streaming(self, pids):
        """ Start the continous perf process to reduce overhead"""
        if self.perf_process or not pids: return

        pid_str = ",".join(map(str, pids))
        cmd = [self.config['perf_bin'], "stat", "-I", "1000", 
               "-e", "cycles:u,instructions:u,cache-misses:u,cache-references:u",
               "-p", pid_str, "-x", ","]
        
        try:
            self.perf_process = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True, bufsize=1)
            file_descriptor = self.perf_process.fileno()
            fl = fcntl.fcntl(file_descriptor, fcntl.F_GETFL)
            fcntl.fcntl(file_descriptor, fcntl.F_SETFL, fl | os.O_NONBLOCK) # Non-blocking read
        except Exception as e:
            print(f"[ERROR] Perf stream failed: {e}")
    
    def read_perf(self):
        """Reads the latest available data from the persistent perf stream"""

        if self.perf_process == None:
            return 0.0, 0.0, 0.0, 0.0
        
        cycles = instr = refs = misses = 0
        data_found = False

        try:
            # Read all lines in the buffer
            while True:
                line = self.perf_process.stderr.readline()
                if not line: break
                parts = line.strip().split(',')
                if len(parts) < 3: continue

                # Timestamp, value, unit, event

                try:
                    val = int(parts[1])
                    event = parts[3]

                    if "cycles" in event: cycles = val
                    elif "instructions" in event: instr = val
                    elif "misses" in event: misses = val
                    elif "references" in event: refs = val
                    data_found = True
                except:
                    continue
        except:
            pass

        # If unable to find new data in this iteration, return cached ipc and miss rate
        if not data_found:
            return self.perf_data['ipc'], self.perf_data['miss'], 0.0, 0.0

        ipc = instr / cycles if cycles > 0 else 0.0
        miss_rate = misses / refs if refs > 0 else 0.0

        # cache the resuylts
        self.perf_data['ipc'] = ipc
        self.perf_data['miss'] = miss_rate

        return ipc, miss_rate, refs, misses

    def sample(self, pids) -> SystemMetrics:
        now = time.time()
        dt = now - self.prev['time']
        if dt <= 0: 
            dt = 0.2

        # Make sure the perf stream is connected
        if not self.perf_process:
            self.start_perf_streaming(pids)

        # 1. Collect perf stream data
        ipc, miss_rate, cache_ref, cache_miss = self.read_perf()

        # Read the raw counter values (use seek(0) for overhead reduction)
        # 2. Get system wide CPU metrics
        self.files['stat'].seek(0)
        cpu_line = self.files['stat'].readline().split()
        curr_cpu = [int(x) for x in cpu_line[1:9]]

        # compute delats
        deltas = [self._safe_delta(c, p, f"cpu_{i}") for i, (c, p) in enumerate(zip(curr_cpu, self.prev['cpu']))]
        total_cpu_delta = sum(deltas)

        if total_cpu_delta > 0:
            cpu_util_all = [100 * d / total_cpu_delta for d in deltas]
            # get the total am,ount besides for idling and io to see how much time was spent doing active work on the cpu
            cpu_total_util = 100 - cpu_util_all[3] - cpu_util_all[4]
        else:
            cpu_util_all = [0] * 8
            cpu_total_util = 0.0

        # 3. THE POWER
        # package poiwer
        curr_pkg = self._read_rapl(self.files['rapl'])
        delta_pkg = self._safe_delta(curr_pkg, self.prev['pkg_e'], "rapl_pkg")
        pkg_watts = delta_pkg / 1e6 / dt

        # dram power (assign state now since the it is the only conditional state)
        dram_watts = 0.0
        if 'dram' in self.files:
            curr_dram = self._read_rapl(self.files['dram'])
            delta_dram = self._safe_delta(curr_dram, self.prev['dram_e'], "rapl_dram")
            dram_watts = delta_dram / 1e6 / dt
            self.prev['dram_e'] = curr_dram
            
        # 4. NETWORK data
        curr_rx, curr_tx = self._read_net()
        delta_rx = self._safe_delta(curr_rx, self.prev['net_r'], "net_rx")
        delta_tx = self._safe_delta(curr_tx, self.prev['net_s'], "net_tx")

        # Convwert in MBs
        net_rx_mbps = delta_rx / dt / MBPS_CONVERSION_FACTOR
        net_tx_mbps = delta_tx / dt / MBPS_CONVERSION_FACTOR

        # 5. Process level metrics (context and sync variance)
        curr_ctx, curr_proc_times = self._get_proc_metrics(pids)

        delta_ctx = self._safe_delta(curr_ctx, self.prev['ctx'], "ctx")
        ctx_rate = delta_ctx / dt

        # sync variance
        sync_var = self._calc_sync_var(curr_proc_times, self.prev['per_proc_cpu'])

        # 6. UPDATE STATE
        self.prev['time'] = now
        self.prev['cpu'] = curr_cpu
        self.prev['pkg_e'] = curr_pkg
        self.prev['net_r'] = curr_rx
        self.prev['net_s'] = curr_tx
        self.prev['ctx'] = curr_ctx
        self.prev['per_proc_cpu'] = curr_proc_times

        return SystemMetrics(
            timestamp=now,
            ipc=ipc,
            miss_rate=miss_rate,
            cache_ref=cache_ref,
            cache_miss=cache_miss,
            cpu_util_all=cpu_util_all,
            cpu_total_util=cpu_total_util,
            iowait_pct=0.0,
            pkg_power=pkg_watts,
            dram_power=dram_watts,
            net_rx_mbps=net_rx_mbps,
            net_tx_mbps=net_tx_mbps,
            active_ranks=len(pids),
            ctx_switches=ctx_rate,
            sync_variance=sync_var
        )



    # ---------------------- Helper Functions Begin----------------------
    def _safe_delta(self, current, previous, counter_name=""):
        if current >= previous: return current - previous
        max_value = 2**32 if "energy" in counter_name or "rapl" in counter_name.lower() else 2**64
        return (max_value - previous) + current

    def _read_rapl(self, handle):
        """Read rapl without reopeing the file"""
        if not handle: 
            return 0
        
        try:
            handle.seek(0)
            return int(handle.read().strip())
        except: return 0 

    def _read_net(self):
        """ Getv the sum of the bytes for all bnetwork interfaces"""

        total_rx, total_tx = 0, 0

        try:
            self.files['net'].seek(0)
            # no need for the header lines
            lines = self.files['net'].readlines()[2:]

            for line in lines:
                parts = line.split()
                if not parts:
                    continue
                iface = parts[0].strip(":")

                if iface in NETWORK_INTERFACES:
                    total_rx += int(parts[1])
                    total_tx = int(parts[9])

        except: 
            pass
        return total_rx, total_tx
    
    def _cleanup_pids(self, pids):
        """ Returns context sqiucthes and cpu time per process"""
        

        # clean up any dead pids
        curr_pids = set(pids)
        for pid in list(self.proc_handles.keys()):
            if pid not in curr_pids:
                try:
                    self.proc_handles[pid]['stat'].close()
                except:
                    pass

                try:
                    self.proc_handles[pid]['status'].close()
                except:
                    pass

                del self.proc_handles[pid]

    def _get_proc_metrics(self, pids):
        # Clean up old PIDs first
        self._cleanup_pids(pids)

        total_ctx = 0
        proc_times = {}

        for pid in pids:
            # 1. Open handles if new PID
            if pid not in self.proc_handles:
                try:
                    self.proc_handles[pid] = {
                        'stat': open(f"/proc/{pid}/stat", 'r'),
                        'status': open(f"/proc/{pid}/status", 'r'),
                    }
                except:
                    continue

            # 2. Get CPU time from stat
            try:
                f_stat = self.proc_handles[pid]['stat']
                f_stat.seek(0)
                data = f_stat.read().split()
                if len(data) > 14: # Basic safety check
                    proc_times[pid] = int(data[13]) + int(data[14])
            except:
                pass
            
            # 3. Get Context Switches from status
            try:
                f_status = self.proc_handles[pid]['status']
                f_status.seek(0)
                for line in f_status:
                    if "voluntary_ctxt_switches" in line:
                        total_ctx += int(line.split()[1])
                    elif "nonvoluntary_ctxt_switches" in line:
                        total_ctx += int(line.split()[1])
            except:
                pass
        
        return total_ctx, proc_times
    
    def _calc_sync_var(self, curr_times, prev_times):
        """Variance of cpu time consumed by each rank in interval"""
        deltas = []

        for pid, val in curr_times.items():
            if pid in prev_times:
                delta = max(val - prev_times[pid], 0)
                deltas.append(delta)
            
        if len(deltas) < 2:
            return 0.0
        
        avg = statistics.mean(deltas)
        if avg == 0: 
            return 0.0
        
        # Get the norm variance
        try:
            variance = statistics.variance(deltas, avg)
            return (variance / avg * 100)
        except:
            return 0.0

   # ---------------------- Helper Functions END----------------------

class PhaseAnalyzer:
    def __init__(self):
        pass