#!/usr/bin/env python3
import time
from pathlib import Path
import subprocess

# ========= CONFIG =========
INTERVAL = 0.1               # seconds between samples
CORE_BUSY_THRESH = 50      # a core is "busy" if >= this %
BUSY_FRACTION = 0.25          # require >= this fraction of cores busy (0.5 = half)
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

def get_minife_pids():
    """Return list of PIDs for running miniFE processes."""
    try:
        out = subprocess.check_output(["pgrep", "miniFE"]).decode().strip()
        return [int(pid) for pid in out.split()] if out else []
    except subprocess.CalledProcessError:
        return []
    
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
    """Compute power (W) from RAPL energy counter."""
    if not rapl_ok:
        return 0.0, prev_energy
    try:
        energy = int(RAPL_PKG.read_text().strip())
    except Exception:
        return 0.0, prev_energy

    if prev_energy is None:
        return 0.0, energy

    delta_uj = energy - prev_energy
    if delta_uj < 0:
        delta_uj = 0
    # convert µJ to J, then divide by interval (J/s = W)
    watts = delta_uj / (1e6 * INTERVAL)
    return watts, energy


print("[run] monitoring loop entered. run your OpenMP/MPI miniFE in another shell.")

while True:
    loop_start = time.time()
    ts = loop_start

    # --- read power ---
    watts, prev_energy = read_rapl(prev_energy)

    # --- detect miniFE ranks ---
    pids = get_minife_pids()
    if not pids:
        print("[wait] no miniFE processes found; waiting for mpirun...")
        time.sleep(1)
        continue

    # # --- skip early startup phase ---
    # if len(pids) == 1 and time.time() - loop_start < 2:
    #     continue

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

    # compute deltas
    if "prev_rank_usage" not in locals():
        prev_rank_usage = rank_usage.copy()
        time.sleep(INTERVAL)
        continue

    busy_ranks = 0
    for pid, total_time in rank_usage.items():
        prev_time = prev_rank_usage.get(pid, total_time)
        if total_time - prev_time > 0:
            busy_ranks += 1
    prev_rank_usage = rank_usage.copy()

    # --- treat ranks as cores ---
    busy_cores = busy_ranks
    total_cores = len(pids)
    needed_cores = max(1, int(total_cores * BUSY_FRACTION))

    # learn idle baseline dynamically if not set
    if idle_baseline_w is None and watts > 1.0:
        idle_baseline_w = watts
    elif watts < idle_baseline_w + 2.0:
        # slowly adapt baseline when under light load
        idle_baseline_w = 0.9 * idle_baseline_w + 0.1 * watts

    # --- parallel detection rules ---
    is_parallel = False  # default

    if total_cores > 1 and busy_cores >= needed_cores:
        if rapl_ok and idle_baseline_w is not None:
            if watts >= idle_baseline_w + POWER_MARGIN_W:
                is_parallel = True


    with open("/proc/loadavg") as f:
        la1 = float(f.read().split()[0])
    if is_parallel and la1 < 0.01 and busy_cores < needed_cores:
        is_parallel = False

    # --- print smart updates ---
    if "last_busy" not in locals():
        last_busy, same_count, last_print_time = None, 0, time.time()

    if busy_cores == last_busy:
        same_count += 1
        if time.time() - last_print_time > 10:
            print(f"[Busy Ranks] {busy_cores} (stable {same_count} cycles)")
            last_print_time = time.time()
    else:
        print(f"[Busy Ranks] {busy_cores}")
        last_busy, same_count, last_print_time = busy_cores, 1, time.time()

    # --- streak logic ---
    if is_parallel:
        streak += 1
        if streak >= STREAK_NEEDED:
            baseline_val = idle_baseline_w if idle_baseline_w is not None else 0.0
            print(
                f"[detect] PARALLEL COMPUTE PHASE "
                f"(busy={busy_cores}/{total_cores}, watts={watts:.1f}, baseline={baseline_val:.1f})"
            )
            streak = 0
    else:
        streak = 0

    # --- heartbeat ---
    now = time.time()
    if now - last_hb >= HEARTBEAT_SEC:
        baseline_val = idle_baseline_w if idle_baseline_w is not None else 0.0
        print(
            f"[hb] ranks={total_cores}, busy={busy_cores}, need>={needed_cores}, "
            f"watts={watts:.1f}, baseline={baseline_val:.1f}"
        )
        last_hb = now
    
    phase = "IDLE"

    baseline_val = idle_baseline_w if idle_baseline_w is not None else 0.0
    
    # Serial few cores busy, but power above idle -> single thread ocmpute
    # if busy_cores < needed_cores and avg_power > baseline_val + POWER_MARGIN_W:
    #     phase = "SERIAL"
    if busy_cores == 1 and watts > idle_baseline_w + POWER_MARGIN_W:
        phase = "SERIAL"
    # PARALLEL many cores busy and power is above idle
    elif busy_cores > needed_cores and watts > baseline_val + POWER_MARGIN_W:
        phase = "PARALLEL"
    
    # # I/O: Low power, low utilization, but possibly some activity
    # elif watts < baseline_val + 3 and busy_cores > 0:
    #     phase = "I/O"

    # IDLE: no active ranks
    elif busy_cores == 0:
        phase = "IDLE"
    
    # Print when phase changes
    if "last_phase" not in locals() or phase != last_phase:
        print(f"[phase] {phase:8s} | busy={busy_cores}/{total_cores} | watts={watts:.1f}")
        last_phase = phase

    # maintain timing
    elapsed = time.time() - loop_start
    sleep_time = INTERVAL - elapsed
    if sleep_time > 0:
        time.sleep(sleep_time)
