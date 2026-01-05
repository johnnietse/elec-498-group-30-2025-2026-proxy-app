#!/usr/bin/env python3
import time
from pathlib import Path
import subprocess

# ========= CONFIG =========
INTERVAL = 0.1                  # seconds between samples
CORE_BUSY_THRESH = 50           # (unused here but kept for completeness)
BUSY_FRACTION = 0.25            # require >= this fraction of cores busy (0.5 = half)
POWER_MARGIN_W = 4.0            # watts above idle to call it "real work"
STREAK_NEEDED = 2               # consecutive matching samples
CSV_PATH = "parallel_monitor.csv"
HEARTBEAT_SEC = 5
IOWAIT_LIMIT = 5.0              # if lots of iowait, don't call it compute

UTILIZATION_THRESHOLD = 0.8     # thread is busy for 80% of the monitoring interval
TICKS_IN_INTERVAL = (100 * INTERVAL) 
MIN_TICKS = TICKS_IN_INTERVAL * UTILIZATION_THRESHOLD

PERF = "/cvmfs/soft.computecanada.ca/gentoo/2023/x86-64-v3/usr/bin/perf"
PERF_INTERVAL = 0.05             # perf sampling interval (seconds)

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
print("[startup] monitor-only mode (waiting for miniFE or miniMD).")

prev_cpu = {}       # cpu_id -> (total, idle, iowait)
prev_energy = None
streak = 0
last_hb = time.time()
idle_baseline_w = None   # will be learned dynamically


# =====================================================
#               PROCESS DETECTION HELPERS
# =====================================================

def get_minife_pids():
    """Return PIDs for miniFE or miniMD."""
    pids = []
    for name in ("miniFE", "miniMD"):
        try:
            out = subprocess.check_output(["pgrep", "-f", name]).decode().strip()
            if out:
                pids += [int(pid) for pid in out.split()]
        except subprocess.CalledProcessError:
            pass
    return pids


# =====================================================
#                    SYSTEM READERS
# =====================================================

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
    watts = delta_uj / (1e6 * INTERVAL)
    return watts, energy



def safe_extract(line):
    """Return integer or 0 if unsupported."""
    token = line.split()[0]
    if token.startswith("<") and token.endswith(">"):
        return 0  # <not supported>
    token = token.replace(",", "")
    return int(token) if token.isdigit() else 0

def read_perf_metrics():
    try:
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
    except Exception as e:
        print(f"[Error] {e}")
        return 0.0, 0.0
    

# =====================================================
#            WAIT FOR miniFE / miniMD TO START
# =====================================================

print("[wait] Waiting for MiniFE or MiniMD to start...")

while True:
    pids = get_minife_pids()
    if pids:
        print(f"[start] Detected MiniFE/MiniMD running (PIDs={pids}). Starting monitor...")
        break
    time.sleep(1)

# start of application runtime
application_start = time.time()

# Initialize rank usage tracking
prev_rank_usage = {}

print("[run] Monitoring loop entered.")


# =====================================================
#                   MAIN MONITORING LOOP
# =====================================================
monitor_start = time.time()
while True:
    
    loop_start = time.time()
    ts = loop_start

    # read power
    watts, prev_energy = read_rapl(prev_energy)

    # detect PIDs
    pids = get_minife_pids()
    if not pids:
        print("[stop] MiniFE/MiniMD has finished. Exiting monitor.")
        break

    # per-rank usage
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
    busy_ranks = 0
    for pid, total_time in rank_usage.items():
        prev_time = prev_rank_usage.get(pid, total_time)
        delta_ticks = total_time - prev_time

        # only ccount threads that are active for significant portions of the monitroing interval
        # e.g., in this case at least 8 out of 10 ticks
        if delta_ticks >= MIN_TICKS:
            busy_ranks += 1
    prev_rank_usage = rank_usage.copy()

    busy_cores = busy_ranks
    total_cores = len(pids)
    needed_cores = max(1, int(total_cores * BUSY_FRACTION))

    # learn idle baseline
    if idle_baseline_w is None and watts > 1.0:
        idle_baseline_w = watts
    elif idle_baseline_w is not None and watts < idle_baseline_w + 2.0:
        idle_baseline_w = 0.9 * idle_baseline_w + 0.1 * watts

    # detect parallel compute phase
    is_parallel = False
    if total_cores > 1 and busy_cores >= needed_cores:
        if rapl_ok and idle_baseline_w is not None:
            if watts >= idle_baseline_w + POWER_MARGIN_W:
                is_parallel = True

    # --- streak logic ---
    if is_parallel:
        streak += 1
        if streak >= STREAK_NEEDED:
            baseline_val = idle_baseline_w or 0.0
            print(
                f"[detect] PARALLEL COMPUTE PHASE "
                f"(busy={busy_cores}/{total_cores}, watts={watts:.1f}, baseline={baseline_val:.1f})"
            )
            streak = 0
    else:
        streak = 0

    # heartbeat
    now = time.time()
    if now - last_hb >= HEARTBEAT_SEC:
        baseline_val = idle_baseline_w or 0.0
        print(
            f"[hb] ranks={total_cores}, busy={busy_cores}, need>={needed_cores}, "
            f"watts={watts:.1f}, baseline={baseline_val:.1f}"
        )
        last_hb = now

    # PHASE CLASSIFICATION (timestamped)
    baseline_val = idle_baseline_w or 0.0
    phase = "IDLE"

    ipc,cache_misses = read_perf_metrics()

    if busy_cores == 1 and watts > baseline_val + POWER_MARGIN_W and ipc >= 1.0:
        phase = "SERIAL"
    elif busy_cores > 1 and watts > baseline_val + POWER_MARGIN_W and ipc >= 1.0:
        phase = "PARALLEL"
    elif busy_cores == 0:
        phase = "IDLE"

    # ---- PHASE TRANSITION WITH TIMESTAMP ----
    if "last_phase" not in locals() or phase != last_phase:
        t = round(time.time() - monitor_start, 2)
        print(f"[phase @ {t:6.2f}s] {phase:8s} | busy={busy_cores}/{total_cores} | watts={watts:.1f} | IPC=({ipc})")
        last_phase = phase

    # maintain timing
    elapsed = time.time() - loop_start
    sleep_time = INTERVAL - elapsed
    if sleep_time > 0:
        time.sleep(sleep_time)

# end of application runtime
application_end = time.time()

runtime = application_end - application_start
print(f"Toatl Runtime: {runtime}")