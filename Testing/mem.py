#!/usr/bin/env python3
import time
from pathlib import Path
import subprocess
import csv

# ========= CONFIG =========
PERF_INTERVAL = 1.0          # perf sampling interval (seconds)
IPC_THRESHOLD = 0.8          # below → memory bound
MISS_THRESHOLD = 0.30        # LLC miss rate threshold

POWER_MARGIN_W = 4.0         # above idle -> active compute
BUSY_FRACTION = 0.25         # fraction of MPI ranks that need to be busy
CSV_PATH = "memory_bound_monitor.csv"
HEARTBEAT_SEC = 5

RAPL_PKG = Path("/sys/class/powercap/intel-rapl:0/energy_uj")
PERF = "/cvmfs/soft.computecanada.ca/gentoo/2023/x86-64-v3/usr/bin/perf"

# =====================================================
#            STARTUP LOGIC
# =====================================================

print("[startup] memory-bound parallel monitor starting...")

rapl_ok = RAPL_PKG.exists()
if rapl_ok:
    print(f"[startup] RAPL found at {RAPL_PKG}")
else:
    print("[startup] RAPL NOT found, power detection disabled")

# create CSV
with open(CSV_PATH, "w") as f:
    f.write("timestamp,ipc,miss_rate,energy_J,phase\n")
print(f"[startup] logging to {CSV_PATH}")

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
#                    RAPL POWER READER
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

    # convert µJ → W using perf interval
    watts = delta / (1e6 * PERF_INTERVAL)
    return watts, energy

# =====================================================
#              PERF HARDWARE COUNTER READER
# =====================================================

def safe_extract(line):
    """Return integer or 0 if unsupported."""
    token = line.split()[0]
    if token.startswith("<") and token.endswith(">"):
        return 0  # <not supported>
    token = token.replace(",", "")
    return int(token) if token.isdigit() else 0

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
#            WAIT FOR MPI RANKS TO APPEAR
# =====================================================

print("[startup] waiting for MiniFE/MiniMD to launch...")

while True:
    pids = get_minife_pids()
    if pids:
        print(f"[start] detected ranks: {pids}")
        break
    time.sleep(1)

print("[run] entering monitoring loop...")

# =====================================================
#                   MAIN MONITORING LOOP
# =====================================================

prev_energy = None
last_hb = time.time()
start_time = time.time()

while True:

    # workload still running?
    pids = get_minife_pids()
    if not pids:
        print("[stop] workload finished — exiting.")
        break

    # ---- take perf sample (1s) ----
    ipc, miss_rate = read_perf_metrics()

    # ---- power delta ----
    watts, prev_energy = read_rapl(prev_energy)

    # ---- classify phase ----
    memory_bound = (ipc < IPC_THRESHOLD) or (miss_rate > MISS_THRESHOLD)

    if memory_bound:
        phase = "MEMORY_BOUND"
    elif ipc >= IPC_THRESHOLD and miss_rate < MISS_THRESHOLD:
        phase = "COMPUTE"
    else:
        phase = "IDLE"

    # ---- write CSV ----
    timestamp = round(time.time() - start_time, 2)
    with open(CSV_PATH, "a") as f:
        f.write(f"{timestamp},{ipc:.3f},{miss_rate:.3f},{watts:.4f},{phase}\n")

    # ---- print ----
    print(
        f"[{timestamp:5.1f}s] "
        f"IPC={ipc:.2f} | Miss={miss_rate:.2f} | "
        f"Power={watts:.2f}W | Phase={phase}"
    )

    # ---- heartbeat every 5s ----
    now = time.time()
    if now - last_hb >= HEARTBEAT_SEC:
        print(
            f"[hb] ranks={len(pids)}, ipc={ipc:.2f}, "
            f"miss={miss_rate:.2f}, watts={watts:.2f}, phase={phase}"
        )
        last_hb = now
