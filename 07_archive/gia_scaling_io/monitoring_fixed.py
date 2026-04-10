#!/usr/bin/env python3
import os, time, subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ================= CONFIG =================
APP_PGREP_PATTERN = "miniMD_openmpi"   # match your executable name
CSV_PATH = "storage_io_phaseA.csv"

SAMPLE_INTERVAL = 0.2                 # faster sampling catches bursts
HEARTBEAT_SEC = 5.0

# FIXED: Lowered threshold to detect I/O even during chunk writes with sleep intervals
WCHAR_THRESHOLD_BPS = 0.5 * 1024 * 1024   # 500 KB/s (was 2 MB/s)

# Ignore I/O phase detection for first N seconds (avoid startup false positives)
IGNORE_IO_FIRST_N_SEC = 5.0

# Checkpoint detection parameters
MIN_CHECKPOINT_DURATION_SEC = 30.0  # Match --ckpt_io_duration default
CHECKPOINT_IO_TIMEOUT_SEC = 2.0     # Exit if no I/O for 2 seconds after min duration

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
print("[startup] FIXED: /proc/<pid>/io based I/O phase detection")
print(f"[startup] pattern={APP_PGREP_PATTERN}, interval={SAMPLE_INTERVAL}s")
print(f"[startup] RAPL={'on' if rapl_ok else 'off'}")
print(f"[startup] I/O threshold: {WCHAR_THRESHOLD_BPS/1e6:.2f} MB/s (lowered to catch chunk writes)")
print(f"[startup] Ignoring I/O detections in first {IGNORE_IO_FIRST_N_SEC}s (startup noise)")
print(f"[startup] Checkpoint min duration: {MIN_CHECKPOINT_DURATION_SEC}s")
print(f"[startup] Exit timeout: {CHECKPOINT_IO_TIMEOUT_SEC}s after min duration")
print(f"[startup] logging to {CSV_PATH}")

with open(CSV_PATH, "w") as f:
    f.write("t_s,dt_s,ranks,wchar_MBps,phase,power_W,checkpoint_MB\n")

print("[startup] waiting for MiniMD to launch...")
while True:
    pids = get_pids()
    if pids:
        break
    time.sleep(0.5)

print(f"[run] MiniMD detected — ranks={len(pids)}")

last: Dict[int, int] = {}
for pid in pids:
    snap = read_proc_io(pid)
    if snap is not None:
        last[pid] = snap

t0 = time.time()
last_t = t0
last_hb = t0
prev_energy = None

# Checkpoint phase tracking (IMPROVED)
in_checkpoint = False
checkpoint_start_time = None
last_io_time = None
checkpoint_bytes_written = 0

while True:
    pids = get_pids()
    if not pids:
        print("[stop] MiniMD finished — exiting.")
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
    # FIXED PHASE LOGIC: Handles sleep intervals between chunks properly
    # ============================================================
    
    # Check if we detect I/O activity (and not in startup period)
    io_detected = (wchar_Bps >= WCHAR_THRESHOLD_BPS) and (t >= IGNORE_IO_FIRST_N_SEC)
    
    if io_detected and not in_checkpoint:
        # Start of checkpoint phase
        in_checkpoint = True
        checkpoint_start_time = now
        last_io_time = now
        checkpoint_bytes_written = 0
        phase = "CHECKPOINT_IO"
        print(f"[PHASE] Entered CHECKPOINT_IO at t={t:.2f}s")
        
    elif in_checkpoint:
        # Track I/O activity
        if io_detected:
            last_io_time = now
            checkpoint_bytes_written += total_dwchar
        
        time_in_checkpoint = now - checkpoint_start_time
        time_since_last_io = now - last_io_time if last_io_time else 0
        
        # Exit conditions:
        # 1. Been in checkpoint >= MIN_CHECKPOINT_DURATION_SEC AND
        # 2. No I/O detected for >= CHECKPOINT_IO_TIMEOUT_SEC
        #
        # This ensures we stay in CHECKPOINT_IO during sleep intervals!
        if (time_in_checkpoint >= MIN_CHECKPOINT_DURATION_SEC and 
            time_since_last_io >= CHECKPOINT_IO_TIMEOUT_SEC):
            in_checkpoint = False
            checkpoint_MB = checkpoint_bytes_written / 1e6
            print(f"[PHASE] Exited CHECKPOINT_IO at t={t:.2f}s (duration={time_in_checkpoint:.2f}s, wrote={checkpoint_MB:.2f} MB)")
            checkpoint_start_time = None
            last_io_time = None
            checkpoint_bytes_written = 0
            phase = "COMPUTE"
        else:
            # Stay in checkpoint phase (handles sleep intervals!)
            phase = "CHECKPOINT_IO"
    else:
        # Not in checkpoint, no I/O detected
        phase = "COMPUTE"

    # Calculate checkpoint MB for CSV
    checkpoint_MB = checkpoint_bytes_written / 1e6 if in_checkpoint else 0

    with open(CSV_PATH, "a") as f:
        f.write(f"{t:.2f},{dt:.3f},{len(pids)},{wchar_MBps:.2f},{phase},{watts:.2f},{checkpoint_MB:.2f}\n")

    # Regular console output
    if now - last_hb >= HEARTBEAT_SEC:
        if in_checkpoint:
            t_in_ckpt = now - checkpoint_start_time
            print(f"[hb] t={t:.2f}s wchar={wchar_MBps:.2f} MB/s phase={phase} "
                  f"ckpt_t={t_in_ckpt:.1f}s ckpt_MB={checkpoint_MB:.1f} P={watts:.2f}W")
        else:
            print(f"[hb] t={t:.2f}s wchar={wchar_MBps:.2f} MB/s phase={phase} P={watts:.2f}W")
        last_hb = now
