#!/usr/bin/env python3
import os, time, subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ================= CONFIG =================
APP_PGREP_PATTERN = "miniMD_openmpi"   # match your executable name
CSV_PATH = "storage_io_phaseA.csv"

SAMPLE_INTERVAL = 0.2                 # faster sampling catches bursts
HEARTBEAT_SEC = 5.0

# Thresholds (tune after 1 run)
# Use wchar (bytes issued to write()) because it's the most reliable
WCHAR_THRESHOLD_BPS = 2 * 1024 * 1024   # 2 MB/s across all ranks

# Ignore I/O phase detection for first N seconds (avoid startup false positives)
IGNORE_IO_FIRST_N_SEC = 5.0

# Once in CHECKPOINT_IO phase, stay in it for at least this long
# This handles the sleep intervals between chunk writes
MIN_CHECKPOINT_DURATION_SEC = 30.0  # Match --ckpt_ioscale_sec default

# Optional RAPL
RAPL_PKG = Path("/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj")
rapl_ok = RAPL_PKG.exists()

# ================ HELPERS =================
def get_pids() -> List[int]:
    try:
        out = subprocess.check_output(
            ["pgrep", "-u", os.getenv("USER", ""), "-f", APP_PGREP_PATTERN],
            text=True
        ).strip()
        if not out:
            return []
        return sorted({int(x) for x in out.split() if x.isdigit()})
    except subprocess.CalledProcessError:
        return []

def read_proc_io(pid: int) -> Optional[int]:
    """
    Return wchar only - simplified
    """
    p = Path(f"/proc/{pid}/io")
    try:
        txt = p.read_text()
    except FileNotFoundError:
        return None

    wchar = 0
    for line in txt.splitlines():
        if line.startswith("wchar:"):
            wchar = int(line.split()[1])
            break
    return wchar

def read_rapl(prev: Optional[int], dt: float) -> Tuple[float, Optional[int]]:
    if not rapl_ok:
        return 0.0, prev
    try:
        e = int(RAPL_PKG.read_text().strip())
    except Exception:
        return 0.0, prev
    if prev is None:
        return 0.0, e
    d = e - prev
    if d < 0:
        d = 0
    watts = (d / 1e6) / max(dt, 1e-6)
    return watts, e

# ================== MAIN ==================
print("[startup] Option A: /proc/<pid>/io based I/O phase detection")
print(f"[startup] pattern={APP_PGREP_PATTERN}, interval={SAMPLE_INTERVAL}s")
print(f"[startup] RAPL={'on' if rapl_ok else 'off'}")
print(f"[startup] Ignoring I/O detections in first {IGNORE_IO_FIRST_N_SEC}s (startup noise)")
print(f"[startup] Checkpoint duration: {MIN_CHECKPOINT_DURATION_SEC}s (stays in I/O phase during sleep)")
print(f"[startup] logging to {CSV_PATH}")

with open(CSV_PATH, "w") as f:
  f.write("t_s,dt_s,ranks,wchar_MBps,phase,power_W\n")

print("[startup] waiting for MiniMD to launch...")
while True:
    pids = get_pids()
    if pids:
        break
    time.sleep(0.5)

print(f"[run] MiniMD detected – ranks={len(pids)}")

last: Dict[int, int] = {}
for pid in pids:
    snap = read_proc_io(pid)
    if snap is not None:
        last[pid] = snap

t0 = time.time()
last_t = t0
last_hb = t0
prev_energy = None

# Checkpoint phase tracking
in_checkpoint = False
checkpoint_start_time = None

while True:
  pids = get_pids()
    if not pids:
        print("[stop] MiniMD finished – exiting.")
        break

    time.sleep(SAMPLE_INTERVAL)
    now = time.time()
    dt = now - last_t
    last_t = now

    # refresh baseline for any new pids
    for pid in pids:
        if pid not in last:
            snap = read_proc_io(pid)
            if snap is not None:
                last[pid] = snap

    total_dwchar = 0

    for pid in pids:
        cur = read_proc_io(pid)
        if cur is None:
            continue
        pwchar = last.get(pid, cur)
        wchar = cur

        total_dwchar += max(0, wchar - pwchar)

        last[pid] = cur

    wchar_Bps = total_dwchar / max(dt, 1e-6)
    wchar_MBps = wchar_Bps / 1e6

    watts, prev_energy = read_rapl(prev_energy, dt)

    t = now - t0

    # ============================================================
    # IMPROVED PHASE LOGIC: Handle sleep intervals during checkpoint
    # ============================================================
    
    # Check if we detect I/O activity (and not in startup period)
    io_detected = (wchar_Bps >= WCHAR_THRESHOLD_BPS) and (t >= IGNORE_IO_FIRST_N_SEC)
    
    if io_detected and not in_checkpoint:
        # Start of checkpoint phase
        in_checkpoint = True
        checkpoint_start_time = now
        phase = "CHECKPOINT_IO"
    elif in_checkpoint:
        # Already in checkpoint - check if we should exit
        time_in_checkpoint = now - checkpoint_start_time
        
        if time_in_checkpoint >= MIN_CHECKPOINT_DURATION_SEC:
            # Checkpoint duration elapsed, can exit phase
            if not io_detected:
                # No more I/O detected, exit checkpoint phase
                in_checkpoint = False
                checkpoint_start_time = None
                phase = "COMPUTE"
            else:
                # Still seeing I/O, stay in checkpoint (maybe another checkpoint started)
                phase = "CHECKPOINT_IO"
        else:
            # Still within checkpoint duration - STAY IN CHECKPOINT_IO
            # This handles the sleep intervals!
            phase = "CHECKPOINT_IO"
    else:
        # Not in checkpoint, no I/O detected
        phase = "COMPUTE"

    with open(CSV_PATH, "a") as f:
        f.write(f"{t:.2f},{dt:.3f},{len(pids)},{wchar_MBps:.2f},{phase},{watts:.2f}\n")

    print(f"[{t:6.2f}s] ranks={len(pids)} wchar={wchar_MBps:6.2f} MB/s "
          f"P={watts:6.2f}W phase={phase}")

    if now - last_hb >= HEARTBEAT_SEC:
        print(f"[hb] wchar={wchar_MBps:.2f} MB/s phase={phase}")
        last_hb = now
