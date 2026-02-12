#!/usr/bin/env python3
import os
import sys
import time
import struct
import argparse
import subprocess
import signal
import threading
import ctypes
import math
from ctypes import c_int, c_uint16, c_uint32, c_uint64, c_longlong

# ================= CONFIGURATION =================
APP_NAME = "miniMD"
LOOP_SLEEP = 0.5    # The "I" interval from the paper
PWM_RESOLUTION = 0.01 # Check for frequency switches every 10ms

# Available Discrete Frequencies (Sorted)
FREQ_AVAIL = [1200000, 1600000, 2000000] 

# Explicit Definitions for Logic
FREQ_MIN = 1200000
FREQ_MID = 1600000
FREQ_MAX = 2000000

# Thresholds
GLOBAL_IO_THRESHOLD_MB = 15.0 
UTIL_IDLE_THRESHOLD = 10.0     
IPC_MEM_BOUND = 0.8            
IPC_MIXED = 1.0                

# Beta Config
SLOWDOWN_LIMIT = 0.05  # 'delta' in the paper (5%)

# ================= LOW LEVEL PERF =================
PERF_TYPE_HARDWARE = 0
PERF_COUNT_HW_CPU_CYCLES = 0
PERF_COUNT_HW_INSTRUCTIONS = 1
__NR_perf_event_open = 298

class PerfEventAttr(ctypes.Structure):
    _fields_ = [("type", c_uint32), ("size", c_uint32), ("config", c_uint64),
                ("sample_period", c_uint64), ("sample_type", c_uint64), ("read_format", c_uint64),
                ("flags", c_uint64), ("wakeup_events", c_uint32), ("bp_type", c_uint32),
                ("bp_addr", c_uint64), ("bp_len", c_uint64), ("branch_sample_type", c_uint64),
                ("sample_regs_user", c_uint64), ("sample_stack_user", c_uint32),
                ("clockid", c_int), ("sample_regs_intr", c_uint64),
                ("aux_watermark", c_uint32), ("sample_max_stack", c_uint16), ("reserved2", c_uint16)]

libc = ctypes.CDLL(None)

def perf_event_open(attr, pid, cpu, group_fd, flags):
    attr.size = ctypes.sizeof(attr)
    return libc.syscall(__NR_perf_event_open, ctypes.byref(attr), c_int(pid), c_int(cpu), c_int(group_fd), c_longlong(flags))

# ================= HARDWARE MONITORS =================
class CoreUtilMonitor:
    def __init__(self, cores):
        self.cores = set(cores)
        self.prev = {}
        try: self.f = open("/proc/stat", "r")
        except: pass

    def sample(self):
        if not hasattr(self, 'f'): return {}
        self.f.seek(0)
        res = {}
        for line in self.f:
            if not line.startswith("cpu"): continue
            parts = line.split()
            if len(parts[0]) == 3: continue 
            c = int(parts[0][3:])
            if c not in self.cores: continue
            idle = int(parts[4]) + int(parts[5])
            total = sum(int(x) for x in parts[1:])
            if c in self.prev:
                dt = total - self.prev[c][0]
                di = idle - self.prev[c][1]
                res[c] = (1.0 - (di/dt))*100.0 if dt > 0 else 0.0
            self.prev[c] = (total, idle)
        return res

class IODetector:
    def __init__(self):
        self.handles = {}
        self.last_wchar = {}

    def get_write_mb(self, pids, dt):
        if dt <= 0: return 0.0
        for pid in pids:
            if pid not in self.handles:
                try: self.handles[pid] = open(f"/proc/{pid}/io", "r")
                except: pass
        
        total_delta = 0
        for pid in list(self.handles.keys()):
            if pid not in pids:
                try: self.handles[pid].close()
                except: pass
                del self.handles[pid]
                if pid in self.last_wchar: del self.last_wchar[pid]
                continue
            try:
                f = self.handles[pid]
                f.seek(0)
                for line in f:
                    if line.startswith("wchar:"):
                        val = int(line.split()[1])
                        if pid in self.last_wchar:
                            delta = val - self.last_wchar[pid]
                            if delta > 0: total_delta += delta
                        self.last_wchar[pid] = val
                        break
            except: pass
        return (total_delta / 1024 / 1024) / dt

# ================= IPC MONITOR =================
class ProcessIPC:
    def __init__(self, pid):
        self.pid = pid
        self.fd_instr = self._open(PERF_COUNT_HW_INSTRUCTIONS)
        self.fd_cycles = self._open(PERF_COUNT_HW_CPU_CYCLES)
        self.prev_i = 0
        self.prev_c = 0
        self.valid = (self.fd_instr > 0 and self.fd_cycles > 0)

    def _open(self, cfg):
        attr = PerfEventAttr()
        attr.type = PERF_TYPE_HARDWARE
        attr.config = cfg
        attr.flags = (1 << 0) | (1 << 5) | (1 << 6)
        fd = perf_event_open(attr, self.pid, -1, -1, 0)
        if fd > 0: libc.ioctl(fd, 0x2400, 0)
        return fd

    def _read(self, fd):
        if fd < 0: return 0
        try: return struct.unpack('q', os.read(fd, 8))[0]
        except: return 0

    def get_metrics(self):
        curr_i = self._read(self.fd_instr)
        curr_c = self._read(self.fd_cycles)
        di = curr_i - self.prev_i
        dc = curr_c - self.prev_c
        self.prev_i = curr_i
        self.prev_c = curr_c
        
        ipc = (di / dc) if dc > 0 else 0.0
        return ipc, di

    def close(self):
        if self.fd_instr > 0: os.close(self.fd_instr)
        if self.fd_cycles > 0: os.close(self.fd_cycles)

# ================= BETA OPTIMIZER =================
class BetaOptimizer:
    def __init__(self):
        self.mips_table = {f: 0.0 for f in FREQ_AVAIL}
        self.beta = 1.0

    def update(self, current_freq, mips):
        if current_freq not in self.mips_table or mips <= 0: return
        self.mips_table[current_freq] = mips
        
        # Calculate Beta using MAX and MID (standard approach)
        mips_max = self.mips_table[FREQ_MAX]
        # Find the next available frequency below max for beta calc
        f_next = FREQ_AVAIL[-2] 
        mips_next = self.mips_table[f_next]

        if mips_max == 0 or mips_next == 0: return

        # Beta = ( (f_max/f_next) - 1 ) / ( (mips_max/mips_next) - 1 )
        x = (FREQ_MAX / f_next) - 1.0
        y = (mips_max / mips_next) - 1.0
        
        if abs(x) > 1e-9:
            self.beta = y / x
        else:
            self.beta = 1.0
        
        self.beta = max(0.01, min(2.0, self.beta))

    def get_f_star(self):
        # Calculate optimal frequency f*
        # f* = f_max / (1 + delta / beta)
        delta = SLOWDOWN_LIMIT
        f_star = FREQ_MAX / (1.0 + delta / self.beta)
        return f_star

    def get_pwm_params(self, f_star):
        # Step 3(a): Figure out fj and fj+1
        # fj <= f* < fj+1
        
        # Clamp f_star within hardware limits
        f_star = max(FREQ_AVAIL[0], min(FREQ_AVAIL[-1], f_star))

        # Find neighbors
        f_j = FREQ_AVAIL[0]
        f_next = FREQ_AVAIL[-1]
        
        for i in range(len(FREQ_AVAIL) - 1):
            if FREQ_AVAIL[i] <= f_star <= FREQ_AVAIL[i+1]:
                f_j = FREQ_AVAIL[i]
                f_next = FREQ_AVAIL[i+1]
                break
        
        # Edge case: exact match
        if f_j == f_next:
            return f_j, f_next, 1.0

        # Step 3(b): Compute ratio r
        # Formula: r = [ (1 + delta/beta)/f_max - 1/f_next ] / [ 1/fj - 1/f_next ]
        
        delta = SLOWDOWN_LIMIT
        term_target = (1.0 + delta / self.beta) / FREQ_MAX
        term_next = 1.0 / f_next
        term_j = 1.0 / f_j
        
        numerator = term_target - term_next
        denominator = term_j - term_next
        
        if abs(denominator) < 1e-12:
            r = 1.0 # Should not happen given distinct neighbors
        else:
            r = numerator / denominator
            
        # Clamp r [0, 1]
        r = max(0.0, min(1.0, r))
        
        return f_j, f_next, r

# ================= CONTROLLER =================
class Controller:
    def __init__(self, cores):
        self.handles = {}
        self.last = {} # Cache last written freq
        for c in cores:
            try:
                with open(f"/sys/devices/system/cpu/cpu{c}/cpufreq/scaling_governor", 'w') as f:
                    f.write("userspace")
                self.handles[c] = open(f"/sys/devices/system/cpu/cpu{c}/cpufreq/scaling_setspeed", 'w')
                self.last[c] = 0
            except: pass

    def set(self, core, freq):
        # Optimization: Only write if value changed
        if core in self.handles and self.last.get(core) != freq:
            try:
                self.handles[core].seek(0)
                self.handles[core].write(str(int(freq)))
                self.handles[core].flush()
                self.last[core] = freq
            except: pass

    def reset(self):
        for c in self.handles: self.set(c, FREQ_MAX)
    def close(self):
        for h in self.handles.values(): h.close()

# ================= MAIN =================
stop_event = threading.Event()
def signal_handler(signum, frame): stop_event.set()
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def scan_pids(app_name, cores):
    pmap = {}
    try:
        cmd = ["pgrep", "-u", os.environ.get("USER"), "-f", app_name]
        pids = [int(x) for x in subprocess.check_output(cmd, text=True).split()]
        for pid in pids:
            try:
                with open(f"/proc/{pid}/stat", 'r') as f:
                    c = int(f.read().split()[38])
                    if c in cores: pmap[c] = pid
            except: pass
    except: pass
    return pmap

def emulate_pwm(ctl, pwm_map, duration):
    """
    Simultaneously emulates duty cycles for all cores.
    pwm_map: { core_id: (freq_low, freq_high, time_at_low) }
    """
    start = time.time()
    while True:
        now = time.time()
        elapsed = now - start
        
        if elapsed >= duration:
            break
            
        for c, (f_j, f_next, t_low) in pwm_map.items():
            # Step 3(c): Run r*I seconds at f_j
            # Step 3(d): Run (1-r)*I seconds at f_j+1
            
            if elapsed < t_low:
                ctl.set(c, f_j)
            else:
                ctl.set(c, f_next)
                
        time.sleep(PWM_RESOLUTION) # Small sleep to yield CPU

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cores', type=str, required=True)
    parser.add_argument('--heartbeat', action='store_true')
    args = parser.parse_args()

    cores = []
    for part in args.cores.split(','):
        if '-' in part:
            s, e = map(int, part.split('-'))
            cores.extend(range(s, e+1))
        else: cores.append(int(part))
    cores.sort()

    print(f"[*] Beta-Integrated PWM Emulator Started. Cores: {cores}")

    ctl = Controller(cores)
    io_det = IODetector()
    util = CoreUtilMonitor(cores)
    ipc_mons = {} 
    betas = {c: BetaOptimizer() for c in cores}
    
    pmap = scan_pids(APP_NAME, cores)
    for c, pid in pmap.items():
        ipc_mons[c] = ProcessIPC(pid)

    # Prime monitors
    util.sample() 
    last_loop_time = time.time()

    try:
        while not stop_event.is_set():
            # NOTE: We do NOT use time.sleep(LOOP_SLEEP) here.
            # We use the emulate_pwm function at the end of the loop.
            
            now = time.time()
            dt = now - last_loop_time
            last_loop_time = now
            if dt <= 0: dt = 0.001

            # Refresh PIDs
            if len(ipc_mons) < len(cores):
                pmap = scan_pids(APP_NAME, cores)
                for c, pid in pmap.items():
                    if c not in ipc_mons: ipc_mons[c] = ProcessIPC(pid)

            # 1. Gather Metrics
            curr_pids = list(pmap.values())
            io_mb = io_det.get_write_mb(curr_pids, dt)
            u_data = util.sample()

            # 2. Decision & PWM Calculation
            hb = []
            io_override = (io_mb > GLOBAL_IO_THRESHOLD_MB)
            
            # Map for the PWM Emulator: {core: (f_low, f_high, time_at_low)}
            pwm_execution_map = {}

            for c in cores:
                u = u_data.get(c, 0)
                ipc = 0.0
                instr_delta = 0

                if c in ipc_mons:
                    if ipc_mons[c].valid:
                        ipc, instr_delta = ipc_mons[c].get_metrics()
                    else:
                        del ipc_mons[c]

                # Default Logic
                f_target_low = FREQ_MIN
                f_target_high = FREQ_MIN
                ratio_r = 1.0 # 100% at low
                state = "INIT"
                f_star_disp = 0

                if io_override:
                    state = "G_IO"
                    f_target_low, f_target_high = FREQ_MIN, FREQ_MIN
                elif u < UTIL_IDLE_THRESHOLD:
                    state = "IDLE"
                    f_target_low, f_target_high = FREQ_MIN, FREQ_MIN
                elif u <= 1:
                    state = "INAC"
                    f_target_low, f_target_high = FREQ_MIN, FREQ_MIN
                elif ipc < IPC_MEM_BOUND:
                    state = "MEM "
                    f_target_low, f_target_high = FREQ_MID, FREQ_MID
                elif ipc < IPC_MIXED:
                    state = "MIX "
                    f_target_low, f_target_high = FREQ_MID, FREQ_MID
                else:
                    # === BETA OPTIMIZATION LOGIC ===
                    mips = (instr_delta / 1e6) / dt
                    
                    # Get actual last freq to update model
                    # (Approximation: use cached last write)
                    curr_freq = ctl.last.get(c, FREQ_MAX)
                    
                    betas[c].update(curr_freq, mips)
                    
                    # 1. Calculate f*
                    f_star = betas[c].get_f_star()
                    f_star_disp = f_star
                    
                    # 2. Get Neighbors and Ratio r
                    # fj (low), f_next (high), r (ratio for low)
                    f_j, f_next, r = betas[c].get_pwm_params(f_star)
                    
                    f_target_low = f_j
                    f_target_high = f_next
                    ratio_r = r
                    state = f"B{betas[c].beta:.2f}"

                # Calculate time to spend at f_j (Step 3c)
                time_at_low = ratio_r * LOOP_SLEEP
                
                pwm_execution_map[c] = (f_target_low, f_target_high, time_at_low)

                if args.heartbeat:
                    # Format: [State | f* | r | f_low/f_high]
                    f_star_str = f"{f_star_disp/1e6:.2f}G" if f_star_disp > 0 else "---"
                    hb.append(f"C{c}:[{state}|T:{f_star_str}|r:{ratio_r:.2f}|{int(f_target_low/1000)}/{int(f_target_high/1000)}]")

            if args.heartbeat:
                print(f"|IO:{io_mb:.1f}MB| " + " ".join(hb))
                sys.stdout.flush()

            # 3. Actuation (Emulation Loop)
            # This blocks for LOOP_SLEEP seconds, toggling frequencies
            emulate_pwm(ctl, pwm_execution_map, LOOP_SLEEP)

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n[*] Stopping...")
        ctl.reset()
        ctl.close()
        for m in ipc_mons.values(): m.close()

if __name__ == "__main__":
    main()