#!/usr/bin/env python3
import subprocess
import time
import csv
import re
import os
import signal

# ---------------- CONFIG ----------------
CMD = ["mpirun", "--oversubscribe", "-np", "4", "./miniMD_openmpi", "-i", "in.lj.miniMD"]
LOG_FILE = "memory_bound_monitor.csv"
SAMPLE_INTERVAL = 1.0         # seconds
IPC_THRESHOLD = 0.8           # Below this, CPU is likely memory-bound
MISS_THRESHOLD = 0.30         # LLC miss ratio threshold
RAPL_PATH = "/sys/class/powercap/intel-rapl:0/energy_uj"
# ----------------------------------------

def read_energy():
    """Read CPU package energy (microjoules)"""
    try:
        with open(RAPL_PATH, "r") as f:
            return int(f.read().strip())
    except Exception:
        return 0

def parse_perf_output(output):
    """Parse perf stat -e cycles,instructions,LLC-loads,LLC-load-misses"""
    metrics = {"cycles": 0, "instructions": 0, "loads": 0, "misses": 0}
    for line in output.splitlines():
        if "cycles" in line:
            metrics["cycles"] += int(line.split()[0].replace(',', ''))
        elif "instructions" in line:
            metrics["instructions"] += int(line.split()[0].replace(',', ''))
        elif "LLC-loads" in line:
            metrics["loads"] += int(line.split()[0].replace(',', ''))
        elif "LLC-load-misses" in line:
            metrics["misses"] += int(line.split()[0].replace(',', ''))
    return metrics

def main():
    print(f"[INFO] Launching MiniMD command: {' '.join(CMD)}")
    print(f"[INFO] Logging data to {LOG_FILE}")

    # Open CSV file for writing
    with open(LOG_FILE, "w", newline='') as csvfile:
        fieldnames = ["timestamp", "ipc", "miss_rate", "energy_J", "memory_bound"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        # Launch MiniMD in background
        proc = subprocess.Popen(CMD, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        energy_prev = read_energy()
        time_prev = time.time()

        try:
            while proc.poll() is None:  # While MiniMD is running
                # Run perf sampling for 1 second
                PERF = "/cvmfs/soft.computecanada.ca/gentoo/2023/x86-64-v3/usr/bin/perf"
                perf_cmd = [
                    PERF, "stat",
                    "-e", "cycles,instructions,LLC-loads,LLC-load-misses",
                    "sleep", str(SAMPLE_INTERVAL)
                ]
                result = subprocess.run(perf_cmd, capture_output=True, text=True)
                metrics = parse_perf_output(result.stderr)

                # Compute derived metrics
                cycles = metrics["cycles"]
                instr = metrics["instructions"]
                loads = metrics["loads"]
                misses = metrics["misses"]
                ipc = instr / cycles if cycles > 0 else 0
                miss_rate = misses / loads if loads > 0 else 0

                # Read RAPL energy
                energy_now = read_energy()
                delta_E = max(0, energy_now - energy_prev) / 1e6  # convert µJ → J
                energy_prev = energy_now

                # Determine memory-bound status
                memory_bound = "YES" if (ipc < IPC_THRESHOLD or miss_rate > MISS_THRESHOLD) else "NO"

                # Write sample
                timestamp = round(time.time() - time_prev, 2)
                writer.writerow({
                    "timestamp": timestamp,
                    "ipc": round(ipc, 3),
                    "miss_rate": round(miss_rate, 3),
                    "energy_J": round(delta_E, 4),
                    "memory_bound": memory_bound
                })
                csvfile.flush()

                print(f"[{timestamp:5.1f}s] IPC={ipc:.2f}, Miss={miss_rate:.2f}, E={delta_E:.3f}J, Bound={memory_bound}")

        except KeyboardInterrupt:
            print("[INFO] Monitoring interrupted by user.")
        finally:
            proc.send_signal(signal.SIGINT)
            proc.wait()
            print("[INFO] MiniMD run finished.")
            print(f"[INFO] Data logged to {LOG_FILE}")

if __name__ == "__main__":
    main()