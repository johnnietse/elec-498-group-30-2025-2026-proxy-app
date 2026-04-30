# On-Cluster Testing & Energy Measurement Guide
## miniMD Communication Phase — frnt115 HPC Node

Step-by-step guide for testing the communication phase optimization.

---

## Core Layout (32-core node)

```
Core 31:    RESERVED  — HPC maintenance, NO permission to change freq
Core 30:    MONITOR   — Python frequency controller runs here
Cores 0–N:  WORKERS   — MPI processes, 1:1 core-binding

Valid worker counts: 1, 2, 4, 8, 16, 30
  30 = max (core 30 = monitor, core 31 = reserved)
  16 = max power of 2
```

> **IMPORTANT**: All scripts accept the worker count as a parameter.
> Set it once and everything adapts — core ranges, MPI ranks, frequency control.

---

## 1. Login & Navigation

```bash
ssh <your_username>@frnt115
cd /home/hpc6084/frnt115/minimd/ref
```

---

## 2. Copy Modified Files

```bash
# C++ source files
cp /path/to/johnnie-comm-phase/integrate.h   ./
cp /path/to/johnnie-comm-phase/integrate.cpp ./
cp /path/to/johnnie-comm-phase/ljs.cpp       ./

# Python controllers + scripts
cp /path/to/johnnie-comm-phase/integrated_freq_controller.py ./
cp /path/to/johnnie-comm-phase/comm_freq_controller.py       ./
cp /path/to/johnnie-comm-phase/run_freq_tests.sh             ./
cp /path/to/johnnie-comm-phase/verify_file_sizes.py          ./
```

---

## 3. Build

```bash
make openmpi -j 8
```

Produces `miniMD_openmpi`.

---

## 4. Allocate a Node (Slurm)

Replace `N` with your desired worker count (1, 2, 4, 8, 16, or 30):

```bash
# General formula:
salloc --nodes=1 --partition=gpu-rgrant --constraint=lkb \
       --ntasks=N --cpus-per-task=1 --exclusive
```

### Examples:
```bash
# 8 workers:
salloc --nodes=1 --partition=gpu-rgrant --constraint=lkb \
       --ntasks=8 --cpus-per-task=1 --exclusive

# 16 workers (max power of 2):
salloc --nodes=1 --partition=gpu-rgrant --constraint=lkb \
       --ntasks=16 --cpus-per-task=1 --exclusive

# 30 workers (max available):
salloc --nodes=1 --partition=gpu-rgrant --constraint=lkb \
       --ntasks=30 --cpus-per-task=1 --exclusive

# 1 worker (single-core, matching Gia's README):
salloc --nodes=1 --partition=gpu-rgrant --constraint=lkb \
       --ntasks=1 --cpus-per-task=1 --exclusive
```

> **CRITICAL**: Use `--cpus-per-task=1` to ensure core-binding (1 MPI process = 1 CPU core).
> Only core 0 (rank 0) does networking — all others are idle at MPI_Barrier.

---

## 5. Link Checkpoint Directory to Fast Storage

```bash
echo $SLURM_TMPDIR
df -h /lscratch/slurm-job-<YOUR_JOB_ID>
ln -s $SLURM_TMPDIR/chk chk
ls -l chk
```

---

## 6. Run miniMD

Replace `N` with your worker count throughout this section.

### Basic run (comm phase enabled):
```bash
mpirun --oversubscribe -np N --bind-to core \
    ./miniMD_openmpi -i in.lj.miniMD
```

### Examples at different scales:
```bash
# 8 workers:
mpirun --oversubscribe -np 8 --bind-to core \
    ./miniMD_openmpi -i in.lj.miniMD

# 16 workers:
mpirun --oversubscribe -np 16 --bind-to core \
    ./miniMD_openmpi -i in.lj.miniMD

# 30 workers (max):
mpirun --oversubscribe -np 30 --bind-to core \
    ./miniMD_openmpi -i in.lj.miniMD

# 1 worker (single-core):
mpirun --oversubscribe -np 1 ./miniMD_openmpi -i in.lj.miniMD
```

### With custom stand-in size:
```bash
mpirun --oversubscribe -np 16 --bind-to core \
    ./miniMD_openmpi -i in.lj.miniMD --comm_standin_mb 500
```

### Without communication phase (baseline comparison):
```bash
mpirun --oversubscribe -np 16 --bind-to core \
    ./miniMD_openmpi -i in.lj.miniMD --comm_phase 0
```

---

## 7. Run with Frequency Controller

You need **two terminals** (or use `&` to background).

### Terminal 1 — Start the controller (pinned to core 30):

```bash
# Simple controller (Johnnie's comm-only) — N workers:
taskset -c 30 python3 comm_freq_controller.py --workers N

# Full integrated controller (Johnnie + Zane's beta) — N workers:
taskset -c 30 python3 integrated_freq_controller.py --workers N --heartbeat
```

### Examples:
```bash
# 8 workers:
taskset -c 30 python3 integrated_freq_controller.py --workers 8 --heartbeat

# 16 workers:
taskset -c 30 python3 integrated_freq_controller.py --workers 16 --heartbeat

# 30 workers (max):
taskset -c 30 python3 integrated_freq_controller.py --workers 30 --heartbeat

# Dry-run (no frequency changes, just logging):
taskset -c 30 python3 integrated_freq_controller.py --workers 16 --heartbeat --dry-run
```

### Terminal 2 — Run miniMD (matching worker count):
```bash
mpirun --oversubscribe -np N --bind-to core \
    ./miniMD_openmpi -i in.lj.miniMD
```

---

## 8. Run Frequency Tests at 1.2 / 1.6 / 2.0 GHz

```bash
chmod +x run_freq_tests.sh

# 16 workers (default):
./run_freq_tests.sh 16

# 8 workers:
./run_freq_tests.sh 8

# All valid worker counts (run separately):
for n in 1 2 4 8 16 30; do
    ./run_freq_tests.sh $n
done
```

### Manual frequency test (if you can't run the script):
```bash
# Set worker cores 0-(N-1) to 1.2 GHz:
N=16  # your worker count
for c in $(seq 0 $((N-1))); do
    echo "userspace" > /sys/devices/system/cpu/cpu${c}/cpufreq/scaling_governor
    echo "1200000" > /sys/devices/system/cpu/cpu${c}/cpufreq/scaling_setspeed
done
# NOTE: NEVER set core 31 — no permission!

# Verify:
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq

# Run:
mpirun --oversubscribe -np $N --bind-to core \
    ./miniMD_openmpi -i in.lj.miniMD 2>&1 | tee test_1.2ghz_${N}w.log
```

---

## 9. Energy Measurement

### Method 1: RAPL (Running Average Power Limit)

```bash
#!/bin/bash
# Save as: measure_energy.sh
# Usage: ./measure_energy.sh 16  (for 16 workers)

N=${1:-16}  # worker count

BEFORE=$(cat /sys/class/powercap/intel-rapl:0/energy_uj)
START=$(date +%s.%N)

mpirun --oversubscribe -np $N --bind-to core \
    ./miniMD_openmpi -i in.lj.miniMD

END=$(date +%s.%N)
AFTER=$(cat /sys/class/powercap/intel-rapl:0/energy_uj)

ENERGY_UJ=$((AFTER - BEFORE))
ENERGY_J=$(echo "scale=3; $ENERGY_UJ / 1000000" | bc)
DURATION=$(echo "$END - $START" | bc)
POWER=$(echo "scale=3; $ENERGY_J / $DURATION" | bc)

echo ""
echo "=== ENERGY MEASUREMENT ($N workers) ==="
echo "Duration:     ${DURATION}s"
echo "Energy:       ${ENERGY_J}J (${ENERGY_UJ} µJ)"
echo "Avg Power:    ${POWER}W"
echo "========================================"
```

### Method 2: perf stat

```bash
perf stat -e power/energy-pkg/,power/energy-cores/ \
    mpirun --oversubscribe -np 16 --bind-to core \
    ./miniMD_openmpi -i in.lj.miniMD
```

### Method 3: Hardware power meter
Connect to the power strip feeding the HPC node (as in Figure 7).

---

## 10. Verify File Sizes

```bash
# Default (16 workers):
python3 verify_file_sizes.py --nprocs 16

# 8 workers:
python3 verify_file_sizes.py --nprocs 8

# All valid worker counts at once:
python3 verify_file_sizes.py --all-configs
```

---

## 11. Expected Output

```
========================================
COMMUNICATION PHASE (Rank 0 Only)  
========================================
Per-rank data (runtime): X.XX MB
Total data (runtime): X.XX MB [N ranks × per-rank]
Stand-in total: 309.00 MB
NOTE: Runtime total < stand-in. Using stand-in.
Starting MPI loopback send/recv (rank 0 -> rank 0)
...
=== Communication Phase Complete ===
Duration: X.XXX seconds
Effective bandwidth: XXXX.XX MB/s
====================================
```

---

## 12. Cleanup

```bash
rm -rf chk
rm -f phase_marker.txt

# Restore worker cores to max freq (replace N with your count):
N=16
for c in $(seq 0 $((N-1))); do
    echo "2000000" > /sys/devices/system/cpu/cpu${c}/cpufreq/scaling_setspeed
done
# NOTE: Never touch core 31!
```

---

## 13. Test Matrix for Report

| Test | Workers | Freq | Comm Phase | Controller | Purpose |
|------|---------|------|-----------|------------|---------|
| 1 | N | 2.0 GHz | OFF | None | Baseline |
| 2 | N | 2.0 GHz | ON | None | Comm overhead |
| 3 | N | 1.2 GHz | ON | None | Min freq |
| 4 | N | Mixed | ON | `comm_freq_controller.py` | Johnnie's optimization |
| 5 | N | Mixed | ON | `integrated_freq_controller.py` | Full Johnnie+Zane |

Run each test **3 times** for statistical significance.
Suggested worker counts to test: **8, 16, 30** (or all valid: 1, 2, 4, 8, 16, 30).

### Data to record per test:

| Metric | Source |
|--------|--------|
| Total simulation time | `t_total` from PERF_SUMMARY |
| Force compute time | `t_force` from PERF_SUMMARY |
| Communication time | `t_comm` from PERF_SUMMARY |
| Performance (atoms/step/s) | `perf` from PERF_SUMMARY |
| Comm phase duration | "Duration:" from comm output |
| Energy consumed | RAPL or perf stat |
| Average power | Energy / Duration |
