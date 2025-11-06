#!/usr/bin/env python3
import time
from pathlib import Path

# ========= CONFIG =========
INTERVAL = 0.1               # seconds between samples
CORE_BUSY_THRESH = 70.0      # a core is "busy" if >= this %
BUSY_FRACTION = 0.5          # require >= this fraction of cores busy (0.5 = half)
POWER_MARGIN_W = 4.0         # watts above idle to call it "real work"
STREAK_NEEDED = 2            # consecutive matching samples
CSV_PATH = "parallel_monitor.csv"
HEARTBEAT_SEC = 5
IOWAIT_LIMIT = 5.0           # if lots of iowait, don't call it compute
# ==========================

RAPL_PKG = Path("/sys/class/powercap/intel-rapl:0/energy_uj")

print("[startup] parallel monitor starting...")

rapl_ok = RAPL_PKG.exists()
if rapl_ok:
    print(f"[startup] RAPL found at {RAPL_PKG}")
else:
    print("[startup] RAPL NOT found, power filter will be skipped")

# CSV header
with open(CSV_PATH, "w") as f:
    f.write("ts,cpu_id,usage,iowait_pct,watts\n")
print(f"[startup] logging to {CSV_PATH}")

# monitor-only mode
print("[startup] monitor-only mode (run miniFE or other workload in another terminal).")

prev_cpu = {}       # cpu_id -> (total, idle, iowait)
prev_energy = None
streak = 0
last_hb = time.time()
idle_baseline_w = None   # we'll learn this in the first few samples


def read_proc_stat():
    """return dict: cpu_id -> (total, idle, iowait)"""
    cpus = {}
    with open("/proc/stat") as f:
        for line in f:
            if line.startswith("cpu") and line[3].isdigit():
                parts = line.split()
                cpu_id = parts[0]
                user = int(parts[1])
                nice = int(parts[2])
                system = int(parts[3])
                idle = int(parts[4])
                iowait = int(parts[5])
                irq = int(parts[6])
                softirq = int(parts[7])
                steal = int(parts[8])
                total = user + nice + system + idle + iowait + irq + softirq + steal
                cpus[cpu_id] = (total, idle, iowait)
    return cpus


def read_rapl(prev_energy):
    if not rapl_ok:
        return 0.0, prev_energy
    energy = int(RAPL_PKG.read_text().strip())
    if prev_energy is None:
        return 0.0, energy
    delta_uj = energy - prev_energy
    if delta_uj < 0:
        delta_uj = 0
    # for 0.1 s: W ≈ delta_uj / 100000
    watts = delta_uj / 100000.0
    return watts, energy


print("[run] monitoring loop entered. run your OpenMP/MPI miniFE in another shell.")

while True:
    loop_start = time.time()
    ts = loop_start

    cpus = read_proc_stat()
    watts, prev_energy = read_rapl(prev_energy)

    usages = {}
    iowaits = {}
    busy_cores = 0

    # compute per-core usage
    for cpu_id, (total, idle, iowait) in cpus.items():
        if cpu_id in prev_cpu:
            p_total, p_idle, p_iowait = prev_cpu[cpu_id]
            dt = total - p_total
            didle = idle - p_idle
            diowait = iowait - p_iowait
            if dt > 0:
                usage = (100.0 * (dt - didle)) / dt
                iowait_pct = (100.0 * diowait) / dt
            else:
                usage = 0.0
                iowait_pct = 0.0
        else:
            usage = 0.0
            iowait_pct = 0.0

        usages[cpu_id] = usage
        iowaits[cpu_id] = iowait_pct
        prev_cpu[cpu_id] = (total, idle, iowait)

        if usage >= CORE_BUSY_THRESH:
            busy_cores += 1

    # learn idle baseline (first couple samples)
    if idle_baseline_w is None:
        # if node is really idle, watts will be stable ~60-65 on your box
        idle_baseline_w = watts

    # write CSV
    with open(CSV_PATH, "a") as f:
        for cpu_id in usages:
            f.write(f"{ts},{cpu_id},{usages[cpu_id]:.2f},{iowaits[cpu_id]:.2f},{watts:.2f}\n")

    total_cores = len(usages)
    needed_cores = max(1, int(total_cores * BUSY_FRACTION))

    # --- rule checks ---
    is_parallel = True

    # 1) many cores busy
    if busy_cores < needed_cores:
        is_parallel = False

    # 2) power above baseline (if we have it)
    if is_parallel and rapl_ok and idle_baseline_w is not None:
        if watts < idle_baseline_w + POWER_MARGIN_W:
            is_parallel = False

    # 3) not obvious i/o
    if is_parallel:
        # if lots of cores show iowait, it's not compute
        high_iowait_cores = sum(1 for v in iowaits.values() if v > IOWAIT_LIMIT)
        if high_iowait_cores > 0:
            is_parallel = False

    # 4) small loadavg filter (optional)
    with open("/proc/loadavg") as f:
        la1 = float(f.read().split()[0])
    # if the system is crazy low load but our rule somehow passed, make sure cores match
    if is_parallel and la1 < 0.01 and busy_cores < needed_cores:
        is_parallel = False

    # streaking
    if is_parallel:
        streak += 1
        if streak >= STREAK_NEEDED:
            print(
                f"[detect] PARALLEL COMPUTE PHASE "
                f"(busy={busy_cores}/{total_cores}, watts={watts:.1f}, baseline={idle_baseline_w:.1f})"
            )
            streak = 0
    else:
        streak = 0

    # heartbeat
    now = time.time()
    if now - last_hb >= HEARTBEAT_SEC:
        baseline_val = idle_baseline_w if idle_baseline_w is not None else 0.0
        print(
            f"[hb] cores={total_cores}, busy={busy_cores}, need>={needed_cores}, "
            f"watts={watts:.1f}, baseline={baseline_val:.1f}"
        )
        last_hb = now