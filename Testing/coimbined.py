#!/usr/bin/env python3
import time
from pathlib import Path
import subprocess
import csv

# =====================================================
#                     CONFIG
# =====================================================

INTERVAL = 0.1               # CPU utilization sampling interval
PERF_INTERVAL = 1.0          # perf sampling interval
POWER_MARGIN_W = 4.0
BUSY_FRACTION = 0.25
STREAK_NEEDED = 2
HEARTBEAT_SEC = 5

IPC_THRESHOLD = 0.8          # below = memory bound
MISS_THRESHOLD = 0.30

CSV_PATH = "merged_monitor.csv"

RAPL_PKG = Path("/sys/class/powercap/intel-rapl:0/energy_uj")
PERF = "/cvmfs/soft.computecanada.ca/gentoo/2023/x86-64-v3/usr/bin/perf"

# =====================================================
#                     STARTUP
# =====================================================

print("[startup] merged memory + CPU parallel monitor starting...")

rapl_ok = RAPL_PKG.exists()
print(f"[startup] RAPL {'FOUND' if rapl_ok else 'NOT FOUND'} at {RAPL_PKG}")

# create CSV
with open(CSV_PATH, "w") as f:
    f.write("timestamp,ipc,miss_rate,watts,busy_cores,total_cores,phase\n")
print(f"[startup] logging to {CSV_PATH}")


# =====================================================
#               PROCESS DETECTION
# =====================================================

def get_minife_pids():
    pids = []
    for name in ("miniFE", "miniMD"):
        try:
            out = subprocess.check_output(["pgrep", "-f", name]).decode().strip()
            if out:
                pids.extend(int(pid) for pid in out.split())
        except subprocess.CalledProcessError:
            pass
    return pids


print("[wait] Waiting for MiniFE or MiniMD to start...")

while True:
    pids = get_minife_pids()
    if pids:
        print(f"[start] Detected ranks: {pids}")
        break
    time.sleep(1)

print("[run] Monitoring loop entered.")


# =====================================================
#                RAPL POWER READER
# =====================================================

def read_rapl(prev_energy):
    if not rapl_ok:
        return 0.0, prev_energy
    try:
        energy = int(RAPL_PKG.read_text().strip())
    except:
        return 0.0, prev_energy

    if prev_energy is None:
        return 0.0, energy

    delta = energy - prev_energy
    if delta < 0:
        delta = 0

    watts = delta / (1e6 * PERF_INTERVAL)
    return watts, energy


# =====================================================
#              PERF HARDWARE COUNTERS
# =====================================================

def safe_extract(line):
    t = line.split()[0]
    if t.startswith("<") and t.endswith(">"):
        return 0
    t = t.replace(",", "")
    return int(t) if t.isdigit() else 0

def read_perf_metrics():
    cmd = [
        PERF, "stat",
        "-e", "cycles,instructions,LLC-loads,LLC-load-misses",
        "sleep", str(PERF_INTERVAL)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    cycles = instr = loads = misses = 0

    for line in result.stderr.splitlines():
        if "cycles" in line:
            cycles = safe_extract(line)
        elif "instructions" in line:
            instr = safe_extract(line)
        elif "LLC-loads" in line:
            loads = safe_extract(line)
        elif "LLC-load-misses" in line:
            misses = safe_extract(line)

    ipc = instr / cycles if cycles > 0 else 0
    miss_rate = misses / loads if loads > 0 else 0
    return ipc, miss_rate


# =====================================================
#               CPU RANK UTILIZATION
# =====================================================

prev_rank_usage = {}

def read_rank_usage(pids):
    rank_usage = {}
    for pid in pids:
        try:
            with open(f"/proc/{pid}/stat") as f:
                parts = f.read().split()
                utime = int(parts[13])
                stime = int(parts[14])
                rank_usage[pid] = utime + stime
        except FileNotFoundError:
            continue
    return rank_usage


# =====================================================
#                 MAIN MONITOR LOOP
# =====================================================

prev_energy = None
last_hb = time.time()
idle_baseline_w = None
start_time = time.time()

while True:

    pids = get_minife_pids()
    if not pids:
        print("[stop] Workload finished. Exiting.")
        break

    # -----------------------------------
    # 1) PERF: IPC + LLC MISS
    # -----------------------------------
    ipc, miss_rate = read_perf_metrics()

    # -----------------------------------
    # 2) RAPL power
    # -----------------------------------
    watts, prev_energy = read_rapl(prev_energy)

    # -----------------------------------
    # 3) CPU rank activity (busy cores)
    # -----------------------------------
    rank_usage = read_rank_usage(pids)
    busy_ranks = 0
    for pid, total_time in rank_usage.items():
        prev_time = prev_rank_usage.get(pid, total_time)
        if total_time - prev_time > 0:
            busy_ranks += 1
    prev_rank_usage = rank_usage.copy()

    total_cores = len(pids)
    needed_cores = max(1, int(total_cores * BUSY_FRACTION))

    # -----------------------------------
    # 4) dynamic idle power baseline
    # -----------------------------------
    if idle_baseline_w is None and watts > 1.0:
        idle_baseline_w = watts
    elif idle_baseline_w is not None and watts < idle_baseline_w + 2.0:
        idle_baseline_w = 0.9 * idle_baseline_w + 0.1 * watts

    # -----------------------------------
    # 5) Classification logic
    # -----------------------------------

    # Memory-bound classification (perf-based)
    memory_bound = (ipc < IPC_THRESHOLD) or (miss_rate > MISS_THRESHOLD)

    # Compute classification (cores + power)
    high_power = watts > (idle_baseline_w + POWER_MARGIN_W) if idle_baseline_w else False
    parallel_active = busy_ranks >= needed_cores and high_power

    if memory_bound:
        phase = "MEMORY_BOUND"
    elif parallel_active:
        phase = "PARALLEL_COMPUTE"
    elif busy_ranks > 0:
        phase = "COMPUTE"
    else:
        phase = "IDLE"

    # -----------------------------------
    # 6) Logging
    # -----------------------------------

    timestamp = round(time.time() - start_time, 2)
    with open(CSV_PATH, "a") as f:
        f.write(
            f"{timestamp},{ipc:.3f},{miss_rate:.3f},{watts:.3f},"
            f"{busy_ranks},{total_cores},{phase}\n"
        )

    print(
        f"[{timestamp:6.2f}s] "
        f"IPC={ipc:.2f}  Miss={miss_rate:.2f}  "
        f"Busy={busy_ranks}/{total_cores}  "
        f"Pwr={watts:.2f}W  Phase={phase}"
    )

    # Heartbeat
    now = time.time()
    if now - last_hb >= HEARTBEAT_SEC:
        print(
            f"[hb] ranks={total_cores}, ipc={ipc:.2f}, miss={miss_rate:.2f}, "
            f"watts={watts:.2f}, phase={phase}"
        )
        last_hb = now
