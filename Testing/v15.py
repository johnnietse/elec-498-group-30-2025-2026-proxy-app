#!/usr/bin/env python3
"""
INTELLIGENT Communication Phase Monitor for miniMD - Version 16.0
Finalized for Capstone Deployment - Includes Utilization Override Fix
"""

import sys
import subprocess
import importlib.util
import time
import csv
import os
import math
import statistics
import json
import glob
from pathlib import Path
from collections import defaultdict, deque, Counter
from datetime import datetime
import numpy as np

# ============ CONFIGURATION ============
# Ensure -n matches your mpirun -np argument!
CMD = ["mpirun", "--oversubscribe", "-np", "32", 
       "./miniMD_openmpi", "-i", "in.lj.miniMD"]
LOG_FILE = f"comm_phase_monitoring_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
SUMMARY_FILE = f"comm_phase_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
SCALING_FILE = f"scaling_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
SAMPLE_INTERVAL = 0.2

PERF = "/cvmfs/soft.computecanada.ca/gentoo/2023/x86-64-v3/usr/bin/perf"
RAPL_PATH = "/sys/class/powercap/intel-rapl:0/energy_uj"
RAPL_DRAM_PATH = "/sys/class/powercap/intel-rapl:0:0/energy_uj"

FREQ_MAX = "2000000"
FREQ_MIN = "1600000"

POWER_MARGIN_W = 2.0        

# Classification Thresholds
IPC_THRESHOLD = 1.6
MISS_THRESHOLD = 0.30
POWER_MARGIN_THRESHOLD = 1.5
TICKS_PER_SECOND = 100
THREAD_APP_LIMIT = 0.25
MAX_CTX_RATE = 1e6

# Empirical scaling data
EMPIRICAL_SCALING_DATA = {
    32: {"comm_pct": 96.9, "compute_pct": 1.9, "force_pct": 1.9, "neigh_pct": 0.3}
}

NETWORK_INTERFACES = ["ib0", "ib1", "eth0", "eth1", "eno1", "ens1"]

class IntelligentCommPhaseMonitor:
    def __init__(self, expected_ranks=None):
        self.csv_file = None
        self.writer = None
        self.start_time = None
        self.prev_energy = None
        self.prev_task_usage = {}

        self.smoothed_util = 0.0
        self.smoothed_apps = 0.0
        self.smoothing_factor = 0.3

        self.prev_dram_energy = None
        self.prev_proc_stats = {}
        self.prev_net_stats = {}
        self.prev_ctx_switches = [0, 0] 
        self.prev_per_process_cpu = {}
        
        self.has_dram_rapl = os.path.exists(RAPL_DRAM_PATH)
        
        # Phase tracking
        self.current_phase = "INIT"
        self.last_phase = "UNKNOWN"
        self.streak_counter = 0
        self.streak_needed = 2
        self.phase_start_time = None
        self.phase_stats = defaultdict(lambda: {"time": 0.0, "samples": 0, "transitions": 0})
        self.idle_baseline_w = None
        
        # Learning system
        self.power_distribution = []
        self.idle_distribution = []
        self.ctx_distribution = []
        self.sync_distribution = []
        self.ipc_distribution = []
        self.miss_distribution = []
        self.phase_sequence = []

        # Handles
        self.handles = {}
        self.thread_handles = {}
        self.context_handles = {}
        self.governor_paths = None
        self.setspeed_paths = None

        self._init_perma_handles()
        
        # Scaling expectations
        self.expected_ranks = expected_ranks
        if expected_ranks in EMPIRICAL_SCALING_DATA:
            self.expected_comm_pct = EMPIRICAL_SCALING_DATA[expected_ranks]["comm_pct"]
            self.expected_compute_pct = EMPIRICAL_SCALING_DATA[expected_ranks]["compute_pct"]
            print(f"[INFO] Using empirical data: {expected_ranks} ranks => "
                  f"{self.expected_comm_pct:.1f}% comm, {self.expected_compute_pct:.1f}% compute")
        else:
            self.expected_comm_pct = 50.0
            self.expected_compute_pct = 50.0
        
        # Adaptive thresholds default
        self.dynamic_thresholds = {
            'power_comm_threshold': 140.0,
            'power_compute_threshold': 180.0,
            'idle_comm_threshold': 80.0,
            'ctx_comm_threshold': 1000,
            'sync_comm_threshold': 30.0,
            'sync_compute_threshold': 50.0
        }
        
        self.compute_bursts = []
        self.communication_intervals = []
        self.phase_durations_history = defaultdict(list)
        self.network_interfaces = self.detect_network_interfaces()
        
        print(f"[INFO] Detected network interfaces: {self.network_interfaces}")
    
    def _init_perma_handles(self):
        """Open all necessary system handles once."""
        try:
            self.handles['rapl_pkg'] = open(RAPL_PATH, 'r')
            if self.has_dram_rapl:
                self.handles['rapl_dram'] = open(RAPL_DRAM_PATH, 'r')
            self.handles['stat'] = open("/proc/stat", 'r')
            self.handles['net'] = open("/proc/net/dev", 'r')
            
            # Paths for DVFS (Files opened only when writing)
            self.governor_paths = glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor")
            self.setspeed_paths = glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/scaling_setspeed")
            print("[SUCCESS] Application handles established.")
        except Exception as e:
            print(f"[ERROR] Failed to open handles: {e}")
            sys.exit(1)

    def refresh_thread_handles(self, pids):
        """Maintain open handles for thread-level stats."""
        current_tids = set()
        for pid in pids:
            task_path = Path(f"/proc/{pid}/task")
            if task_path.exists():
                for tid_dir in task_path.iterdir():
                    tid = tid_dir.name
                    current_tids.add(tid)
                    if tid not in self.thread_handles:
                        try:
                            self.thread_handles[tid] = open(tid_dir / "stat", 'r')
                        except: continue
        for tid in list(self.thread_handles.keys()):
            if tid not in current_tids:
                self.thread_handles[tid].close()
                del self.thread_handles[tid]

    def set_frequency(self, freq_str):
        """Apply DVFS to all able cores"""
        if not self.governor_paths or not self.setspeed_paths: return
        for gov, speed in zip(self.governor_paths, self.setspeed_paths):
            try:
                with open(gov, "w") as f: f.write("userspace")
                with open(speed, "w") as f: f.write(freq_str)
            except: pass

    def detect_network_interfaces(self):
        interfaces = []
        try:
            with open("/proc/net/dev", "r") as f:
                lines = f.readlines()[2:]
                for line in lines:
                    if ":" in line:
                        iface = line.split(":")[0].strip()
                        if iface in NETWORK_INTERFACES or iface.startswith("ib") or iface.startswith("eth"):
                            interfaces.append(iface)
        except Exception as e:
            print(f"[WARN] Could not read /proc/net/dev: {e}")
        return interfaces
    
    def update_dynamic_thresholds(self, power, idle, ctx_rate, sync_var, ipc, miss_rate):
        """Update thresholds based on observed distributions"""
        self.power_distribution.append(power)
        self.idle_distribution.append(idle)
        self.ctx_distribution.append(ctx_rate)
        self.sync_distribution.append(sync_var)
        self.ipc_distribution.append(ipc)
        self.miss_distribution.append(miss_rate)
        
        if len(self.power_distribution) > 100:
            for dist in [self.power_distribution, self.idle_distribution, self.ctx_distribution, 
                         self.sync_distribution, self.ipc_distribution, self.miss_distribution]:
                dist.pop(0)
        
        if len(self.power_distribution) >= 20 and len(self.power_distribution) % 20 == 0:
            try:
                p25 = np.percentile(self.power_distribution, 25)
                p75 = np.percentile(self.power_distribution, 75)
                
                # FIX 1: Lower the Compute Floor multiplier from 0.98 to 0.90 for safer triggering
                self.dynamic_thresholds['power_compute_threshold'] = p75 * 0.90 
                self.dynamic_thresholds['power_comm_threshold'] = p25 * 1.10
                
                self.dynamic_thresholds['idle_comm_threshold'] = np.percentile(self.idle_distribution, 75)
                self.dynamic_thresholds['ctx_comm_threshold'] = np.percentile(self.ctx_distribution, 75) * 0.8
                self.dynamic_thresholds['sync_compute_threshold'] = np.percentile(self.sync_distribution, 75)
                self.dynamic_thresholds['sync_comm_threshold'] = np.percentile(self.sync_distribution, 25)
                self.dynamic_thresholds['miss_rate_high_target'] = np.percentile(self.miss_distribution, 75)
                self.dynamic_thresholds['ipc_compute_target'] = np.percentile(self.ipc_distribution, 75)
                
                if len(self.power_distribution) % 100 == 0:
                    print(f"[LEARNING] New Compute Floor: {self.dynamic_thresholds['power_compute_threshold']:.1f}W")
            except Exception as e:
                print(f"[WARN] Threshold update failed: {e}")
    
    def get_miniMD_pids(self):
        try:
            result = subprocess.run(["pgrep", "-f", "miniMD"], capture_output=True, text=True, timeout=2)
            if result.returncode == 0 and result.stdout.strip():
                return [int(pid) for pid in result.stdout.strip().split()]
        except: pass
        return []
    
    def safe_delta(self, current, previous, counter_name=""):
        if current >= previous: return current - previous
        # Wrap around handling
        max_value = 2**32 if "energy" in counter_name or "rapl" in counter_name.lower() else 2**64
        return (max_value - previous) + current
    
    def safe_rate(self, curr, prev, dt, counter_name=""):
        if dt <= 0: return 0.0
        delta = self.safe_delta(curr, prev, counter_name)
        rate = delta / dt
        return 0.0 if rate > MAX_CTX_RATE else rate
    
    def read_rapl_energy(self, domain="pkg"):
        """Calculates Power (Watts) using persistent handles."""
        handle_key = 'rapl_pkg' if domain == "pkg" else 'rapl_dram'
        prev_attr = 'prev_energy' if domain == "pkg" else 'prev_dram_energy'
        
        if handle_key not in self.handles: return 0.0
        try:
            h = self.handles[handle_key]
            h.seek(0)
            energy = int(h.read().strip())
            
            prev_val = getattr(self, prev_attr)
            if prev_val is None:
                setattr(self, prev_attr, energy)
                return 0.0
            
            diff = self.safe_delta(energy, prev_val, handle_key)
            setattr(self, prev_attr, energy)
            return diff / (1e6 * SAMPLE_INTERVAL)
        except: return 0.0

    def get_perf_metrics(self, pids):
        if not pids: return 0.0, 0.0
        try:
      
            pid_list_str = ",".join(map(str, pids))
            
            cmd = [PERF, "stat", "-e", "cycles:u,instructions:u,cache-misses:u,cache-references:u", 
                   "-p", pid_list_str, "--", "sleep", "0.1"]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=1.2)

            cycles = instr = refs = misses = 0
            for line in result.stderr.splitlines():
                parts = line.strip().split()
                if not parts: continue
                
                # Perf sums up the counters for all PIDs automatically
                val = int(parts[0].replace(",", "")) if parts[0].replace(",", "").isdigit() else 0
                
                if "cycles" in line: cycles = val
                elif "instructions" in line: instr = val
                elif "cache-misses" in line: misses = val
                elif "cache-references" in line: refs = val
            
            # Now we have the aggregate IPC of the whole application
            ipc = instr / cycles if cycles > 1000 else 0.0
            miss_rate = misses / refs if refs > 1000 else 0.0
            return ipc, miss_rate
        except: return 0.0, 0.0
    
    def get_thread_utilization(self, pids):
        self.refresh_thread_handles(pids)
        total_util = 0.0
        app_threads = 0.0
        current_usage = {}
        ticks_in_interval = TICKS_PER_SECOND * SAMPLE_INTERVAL

        for tid, handle in self.thread_handles.items():
            try:
                handle.seek(0)
                parts = handle.read().split()
                ticks = int(parts[13]) + int(parts[14])
                current_usage[tid] = ticks
                if tid in self.prev_task_usage:
                    util = (ticks - self.prev_task_usage[tid]) / ticks_in_interval
                    total_util += util
                    if util >= THREAD_APP_LIMIT: app_threads += 1
            except: continue
        self.prev_task_usage = current_usage
        return total_util, app_threads

    def read_network_stats(self):
        net_stats = {}
        try:
            self.handles['net'].seek(0)
            lines = self.handles['net'].readlines()[2:]
            for line in lines:
                if ":" in line:
                    parts = line.split()
                    iface = parts[0].replace(":", "")
                    if iface in self.network_interfaces:
                        net_stats[iface] = (int(parts[1]), int(parts[9]))
        except: pass
        return net_stats
    
    def calculate_network_bandwidth(self, prev_stats, curr_stats):
        total_recv = 0
        total_sent = 0
        for iface in self.network_interfaces:
            if iface in prev_stats and iface in curr_stats:
                prev_r, prev_s = prev_stats[iface]
                curr_r, curr_s = curr_stats[iface]
                total_recv += self.safe_delta(curr_r, prev_r, "net_recv")
                total_sent += self.safe_delta(curr_s, prev_s, "net_sent")
        return total_recv / SAMPLE_INTERVAL / 1048576, total_sent / SAMPLE_INTERVAL / 1048576
    
    def get_per_process_cpu_times(self, pids):
        cpu_times = {}
        for pid in pids:
            try:
                with open(f"/proc/{pid}/stat", "r") as f:
                    data = f.read().split()
                    cpu_times[pid] = int(data[13]) + int(data[14])
            except: continue
        return cpu_times
    
    def calculate_sync_variance(self, curr_times, prev_times):
        deltas = []
        for pid, val in curr_times.items():
            if pid in prev_times:
                deltas.append(max(val - prev_times[pid], 0))
        if len(deltas) < 2: return 0.0
        try:
            mean = statistics.mean(deltas)
            return (statistics.variance(deltas, mean) / mean * 100) if mean > 0 else 0.0
        except: return 0.0
    
    def read_proc_stat(self):
        try:
            self.handles['stat'].seek(0)
            parts = self.handles['stat'].readline().split()
            if parts and parts[0] == 'cpu': return [int(x) for x in parts[1:9]]
        except: pass
        return [0]*8
    
    def get_proc_context_switches(self, pids):
        vol = 0
        nonvol = 0
        current_pids = set(pids)
        
        # Cleanup
        for pid in list(self.context_handles.keys()):
            if pid not in current_pids:
                self.context_handles[pid].close()
                del self.context_handles[pid]

        for pid in pids:
            try:
                if pid not in self.context_handles:
                    self.context_handles[pid] = open(f"/proc/{pid}/status", "r")
                f = self.context_handles[pid]
                f.seek(0)
                for line in f:
                    if line.startswith("voluntary_ctxt_switches"):
                        vol += int(line.split()[1])
                    elif line.startswith("nonvoluntary_ctxt_switches"):
                        nonvol += int(line.split()[1])
            except:
                if pid in self.context_handles:
                    self.context_handles[pid].close()
                    del self.context_handles[pid]
        return vol, nonvol
    
    def calculate_cpu_usage(self, prev, curr):
        if not prev or not curr or len(prev) < 8 or len(curr) < 8: return 0,0,100,0
        deltas = [self.safe_delta(c, p, f"cpu_{i}") for i, (p, c) in enumerate(zip(prev, curr))]
        total = sum(deltas)
        if total == 0: return 0,0,100,0
        return (100.0*deltas[0]/total, 100.0*deltas[2]/total, 
                100.0*deltas[3]/total, 100.0*deltas[4]/total)

    def classify_with_adaptive_algorithms(self, pkg_power_W, dram_power_W, cpu_metrics, 
                                          ctx_switch_rate, pids_count, network_bw,
                                          sync_variance_norm, timestamp, ipc, miss_rate, util, apps):
        user_pct, system_pct, idle_pct, iowait_pct = cpu_metrics
        net_recv, net_sent = network_bw
        active_cpu = 100.0 - idle_pct
        total_net = net_recv + net_sent
        
        self.update_dynamic_thresholds(pkg_power_W, idle_pct, ctx_switch_rate, sync_variance_norm, ipc, miss_rate)
        
        dyn_ipc = self.dynamic_thresholds.get('ipc_compute_target', IPC_THRESHOLD)
        dyn_pwr_comp = self.dynamic_thresholds.get('power_compute_threshold', 180.0)
        dyn_pwr_comm = self.dynamic_thresholds.get('power_comm_threshold', 140.0)
        
        if self.idle_baseline_w is None and pkg_power_W > 10: self.idle_baseline_w = pkg_power_W
        baseline = self.idle_baseline_w or 68.0

        # FIX 3: Utilization Fallback
        # If util is close to active_ranks (e.g. 3.9 out of 4), we assume compute
        util_saturation = util / max(1, pids_count)
        
        power_high = pkg_power_W > dyn_pwr_comp
        ipc_high = ipc > dyn_ipc

        # Major Logic Fix: If we are fully saturated, we are computing.
        is_computing = power_high or ipc_high or (util_saturation > 0.85)
        
        is_mem_sig = (ipc < dyn_ipc * 0.5) and (miss_rate > self.dynamic_thresholds.get('miss_rate_high_target', 0.3))
        
        comm_score = 0.0
        comp_score = 0.0
        reasons = []
        
        # Scoring
        if is_computing:
            # If IPC is valid (>0.1), use it for the boost score
            if ipc > 0.1:
                boost = (ipc / dyn_ipc) if dyn_ipc > 0 else 1.0
                comp_score += (2.5 * boost)
                reasons.append(f"compute(IPC={ipc:.2f})")
            else:
                # IPC is dead/0.0 but we are saturated -> FORCE Compute score
                comp_score += 3.0
                reasons.append(f"compute(Util={util:.1f})")
        
        if active_cpu > 20: comp_score += 1.0
        if pkg_power_W > dyn_pwr_comp: comp_score += 1.5
        
        if idle_pct > self.dynamic_thresholds.get('idle_comm_threshold', 80):
            comm_score += 1.5
            reasons.append("high_idle")
        if pkg_power_W < dyn_pwr_comm: comm_score += 1.0
        if total_net > 5: comm_score += 1.0

        # Outliers
        outlier = self.detect_statistical_outliers(pkg_power_W, idle_pct, ctx_switch_rate)
        if outlier > 0.7: comp_score += 2.0
        elif outlier < -0.7: comm_score += 2.0

        # Calibration
        expected_comm_bias = self.expected_comm_pct / 100.0
        comm_score_adj = comm_score * (1.0 + expected_comm_bias)
        comp_score_adj = comp_score

        phase_diff = comm_score_adj - comp_score_adj
        confidence = min(abs(phase_diff)/5.0, 1.0)
        
        # Decision
        if util < 0.15 or idle_pct > 95:
            phase = "IDLE"
            confidence = 0.95
        elif util > 0.4 and is_mem_sig:
            phase = "MEMORY_BOUND"
            confidence = 0.90
            reasons.append("mem_bottleneck")
        elif phase_diff > 1.0:
            phase = "COMMUNICATION"
        elif phase_diff < -1.0:
            phase = "PARALLEL_COMPUTE" if util > 1.1 or apps > 1 else "SERIAL_COMPUTE"
        elif iowait_pct > 15:
            phase = "IO_WAIT"
        else:
            phase = "MIXED"

        phase = self.stabilize_phase(phase, timestamp)

        details = {
            'phase': phase, 'confidence': confidence, 'power_W': pkg_power_W, 'dram_power_W': dram_power_W,
            'cpu_user_pct': user_pct, 'cpu_system_pct': system_pct, 'cpu_idle_pct': idle_pct,
            'cpu_iowait_pct': iowait_pct, 'cpu_active_pct': active_cpu, 
            'voluntary_ctx_switches_per_sec': ctx_switch_rate, 'active_mpi_ranks': pids_count,
            'net_recv_mbps': net_recv, 'net_sent_mbps': net_sent, 'sync_variance_pct': sync_variance_norm,
            'comm_score': comm_score, 'comp_score': comp_score, 'comm_score_adj': comm_score_adj,
            'comp_score_adj': comp_score_adj, 'phase_diff': phase_diff, 'reasons': ','.join(reasons)
        }
        return phase, details

    def detect_statistical_outliers(self, power, idle, ctx_rate):
        if len(self.power_distribution) < 10: return 0.0
        try:
            power_mean = np.mean(self.power_distribution)
            power_std = np.std(self.power_distribution)
            idle_mean = np.mean(self.idle_distribution)
            idle_std = np.std(self.idle_distribution)
            
            p_z = (power - power_mean) / power_std if power_std > 0 else 0
            i_z = (idle - idle_mean) / idle_std if idle_std > 0 else 0
            
            if p_z > 1.5 and i_z < -1.0: return 1.0
            if p_z < -1.5 and i_z > 1.0: return -1.0
            return 0.0
        except: return 0.0

    def stabilize_phase(self, proposed, timestamp):
        self.phase_sequence.append(proposed)
        if len(self.phase_sequence) > 10: self.phase_sequence.pop(0)
        
        if len(self.phase_sequence) >= 3:
            counts = Counter(self.phase_sequence[-3:])
            most_common = counts.most_common(1)[0]
            if most_common[1] >= 2 and most_common[0] != proposed:
                return most_common[0]
        return proposed

    def track_phase_duration(self, phase, timestamp):
        if self.current_phase is None:
            self.current_phase = phase
            self.phase_start_time = timestamp
        elif self.current_phase != phase:
            if self.phase_start_time:
                duration = timestamp - self.phase_start_time
                if duration > 0:
                    self.phase_stats[self.current_phase]["time"] += duration
                    self.phase_stats[self.current_phase]["samples"] += 1
                    self.phase_stats[self.current_phase]["transitions"] += 1
                    self.phase_durations_history[self.current_phase].append(duration)
                    if "COMPUTE" in self.current_phase:
                        self.compute_bursts.append(duration)
                    elif "COMM" in self.current_phase:
                        self.communication_intervals.append(duration)
            self.current_phase = phase
            self.phase_start_time = timestamp

    def setup_csv(self):
        self.csv_file = open(LOG_FILE, "w", newline='')
        fieldnames = [
            'timestamp', 'phase', 'confidence', 'power_W', 'dram_power_W',
            'cpu_user_pct', 'cpu_system_pct', 'cpu_idle_pct', 'cpu_active_pct', 'cpu_iowait_pct',
            'voluntary_ctx_switches_per_sec', 'active_mpi_ranks', 'net_recv_mbps', 'net_sent_mbps',
            'sync_variance_pct', 'comm_score', 'comp_score', 'comm_score_adj', 'comp_score_adj',
            'phase_diff', 'pkg_energy_J', 'dram_energy_J', 'reasons'
        ]
        self.writer = csv.DictWriter(self.csv_file, fieldnames=fieldnames)
        self.writer.writeheader()
        print(f"[INFO] Logging to {LOG_FILE}")

    def generate_scaling_analysis(self):
        # ... [Your existing logic for scaling report] ...
        pass # Placeholder to keep script short, keep your existing method

    def run_monitoring(self):
        self.setup_csv()
        print("[INFO] Waiting for miniMD...")
        while not self.get_miniMD_pids(): time.sleep(0.5)
        
        pids = self.get_miniMD_pids()
        self.start_time = time.time()
        
        # Init baselines
        self.read_rapl_energy(domain="pkg")
        if self.has_dram_rapl: self.read_rapl_energy(domain="dram")
        self.prev_proc_stats = self.read_proc_stat()
        self.prev_net_stats = self.read_network_stats()
        
        sample_count = 0
        try:
            while True:
                loop_start = time.time()
                pids = self.get_miniMD_pids()
                if not pids: break
                
                sample_count += 1
                current_time = time.time() - self.start_time
                
                ipc, miss_rate = self.get_perf_metrics(pids)
                total_util, app_threads = self.get_thread_utilization(pids)
                
                curr_pkg_watts = self.read_rapl_energy(domain="pkg")
                curr_dram_watts = self.read_rapl_energy(domain="dram")
                
                curr_cpu_stats = self.read_proc_stat()
                cpu_metrics = self.calculate_cpu_usage(self.prev_proc_stats, curr_cpu_stats)
                self.prev_proc_stats = curr_cpu_stats
                
                curr_net = self.read_network_stats()
                net_bw = self.calculate_network_bandwidth(self.prev_net_stats, curr_net)
                self.prev_net_stats = curr_net
                
                curr_ctx = self.get_proc_context_switches(pids)
                # FIXED: Using prev_ctx_switches as list index [0]
                ctx_rate = self.safe_rate(curr_ctx[0], self.prev_ctx_switches[0], SAMPLE_INTERVAL)
                self.prev_ctx_switches = list(curr_ctx)
                
                curr_cpu_times = self.get_per_process_cpu_times(pids)
                sync_var = self.calculate_sync_variance(curr_cpu_times, self.prev_per_process_cpu)
                self.prev_per_process_cpu = curr_cpu_times
                
                self.smoothed_util = (self.smoothing_factor * total_util) + (1 - self.smoothing_factor) * self.smoothed_util
                
                phase, details = self.classify_with_adaptive_algorithms(
                    curr_pkg_watts, curr_dram_watts, cpu_metrics, ctx_rate, len(pids),
                    net_bw, sync_var, current_time, ipc, miss_rate, self.smoothed_util, app_threads
                )
                
                self.track_phase_duration(phase, current_time)
                
                # DVFS Logic
                # if phase != self.last_phase:
                #     self.streak_counter += 1
                #     if self.streak_counter >= self.streak_needed:
                #         target = FREQ_MAX if "COMPUTE" in phase else FREQ_MIN
                #         self.set_frequency(target)
                #         self.last_phase = phase
                #         self.streak_counter = 0
                # else:
                #     self.streak_counter = 0
                
                # FIXED: Energy Logging
                details['pkg_energy_J'] = f"{curr_pkg_watts * SAMPLE_INTERVAL:.4f}"
                details['dram_energy_J'] = f"{curr_dram_watts * SAMPLE_INTERVAL:.4f}"
                
                self.writer.writerow(details)
                self.csv_file.flush()
                
                if sample_count % 5 == 0:
                    print(f"[{current_time:6.1f}s] {phase:15s} | Pwr: {curr_pkg_watts:4.0f}W | IPC: {ipc:.2f} | U:{total_util:.1f}")
                
                time.sleep(max(0, SAMPLE_INTERVAL - (time.time() - loop_start)))
        except KeyboardInterrupt:
            print("\n[STOP] Interrupted.")
        finally:
            self.cleanup()

    def cleanup(self):
        print("\n[INFO] Cleanup...")
        if self.csv_file: self.csv_file.close()
        
        # Close handles
        for h in self.handles.values(): 
            try: h.close()
            except: pass
        for h in self.thread_handles.values(): 
            try: h.close()
            except: pass
        for h in self.context_handles.values():
            try: h.close()
            except: pass
            
        # Reset Frequency using PATHS
        if self.governor_paths:
            for g in self.governor_paths:
                try: 
                    with open(g, 'w') as f: f.write("performance")
                except: pass
        
        print("[INFO] Done.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--ranks', type=int, default=32)
    parser.add_argument('-c', '--command', type=str)
    parser.add_argument('-e', '--empirical', action='store_true')
    args = parser.parse_args()
    
    if args.command:
        import shlex
        CMD = shlex.split(args.command)
    
    monitor = IntelligentCommPhaseMonitor(expected_ranks=args.ranks)
    monitor.run_monitoring()