import time
import os
import csv
import subprocess

# --- Configuration ---
FREQUENCIES_GHZ = [1.2, 1.6, 2.4]
ITERATIONS = 10
TOTAL_DATA_MB = 9000
CHUNK_SIZE_MB = 100
MAX_FILE_SIZE_MB = 1000
FILENAME = "io_test.dat"
CSV_OUTPUT = "benchmark_results.csv"
RESERVED_CORE = 0 # Safety check from your provided logic

# --- Frequency Control Functions (Your Logic) ---
def set_freq(core, freq_ghz):
    if core == RESERVED_CORE:
        return False
    path = f"/sys/devices/system/cpu/cpu{core}/cpufreq/scaling_setspeed"
    try:
        # Convert GHz to kHz (standard for scaling_setspeed)
        with open(path, "w") as f:
            f.write(str(int(freq_ghz * 1000000)))
        return True
    except Exception as e:
        print(f"Error setting freq on core {core}: {e}")
        return False

def set_governor(core, gov):
    if core == RESERVED_CORE:
        return False
    path = f"/sys/devices/system/cpu/cpu{core}/cpufreq/scaling_governor"
    try:
        with open(path, "w") as f:
            f.write(gov)
        return True
    except Exception as e:
        print(f"Error setting governor on core {core}: {e}")
        return False

# --- Energy Measurement ---
def get_energy_joules():
    # RAPL counter for the CPU package
    path = "/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj"
    try:
        with open(path, "r") as f:
            return int(f.read()) / 1_000_000.0
    except:
        return 0.0

# --- Core Logic ---
def run_io_test():
    total_bytes = TOTAL_DATA_MB * 1024 * 1024
    chunk_size = CHUNK_SIZE_MB * 1024 * 1024
    max_file_size = MAX_FILE_SIZE_MB * 1024 * 1024
    data_chunk = bytearray(os.urandom(chunk_size))
    
    written_so_far = 0
    current_file_pos = 0

    energy_start = get_energy_joules()
    time_start = time.perf_counter()

    with open(FILENAME, "wb") as f:
        while written_so_far < total_bytes:
            f.write(data_chunk)
            written_so_far += chunk_size
            current_file_pos += chunk_size
            if current_file_pos >= max_file_size:
                f.seek(0)
                current_file_pos = 0
        f.flush()
        os.fsync(f.fileno())
    
    duration = time.perf_counter() - time_start
    energy_end = get_energy_joules()
    return duration, (energy_end - energy_start)

# --- Main Execution ---
# Detect the core assigned by taskset
affinity = os.sched_getaffinity(0)
if not affinity:
    print("Could not detect CPU affinity. Exiting.")
    exit(1)

# Get the first (and likely only) core from taskset
monitor_core = list(affinity)[0]
print(f"Detected Taskset Core: {monitor_core}")

with open(CSV_OUTPUT, "w", newline='') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=["Frequency_GHz", "Iteration", "Time_Sec", "Rate_MBs", "Energy_Joules"])
    writer.writeheader()

    # Step 1: Set the specific core to userspace
    if not set_governor(monitor_core, "userspace"):
        print(f"Failed to set core {monitor_core} to userspace. Check permissions.")
        exit(1)

    for ghz in FREQUENCIES_GHZ:
        print(f"\nScaling Core {monitor_core} to {ghz} GHz...")
        set_freq(monitor_core, ghz)
        time.sleep(2) # Stabilization

        for i in range(1, ITERATIONS + 1):
            duration, energy = run_io_test()
            rate = TOTAL_DATA_MB / duration
            
            writer.writerow({
                "Frequency_GHz": ghz,
                "Iteration": i,
                "Time_Sec": round(duration, 4),
                "Rate_MBs": round(rate, 2),
                "Energy_Joules": round(energy, 4)
            })
            csvfile.flush()
            print(f"  Run {i}: {rate:.2f} MB/s | {duration:.2f}s | {energy:.2f} J")

print(f"\nBenchmark finished. Results in {CSV_OUTPUT}")
