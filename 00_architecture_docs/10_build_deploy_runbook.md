# 10_build_deploy_runbook.md — Build, Deploy, and Operational Runbook

**Scope:** Complete operational guide for building, deploying, and running the miniMD DVFS system on the CAC Frontenac HPC cluster.

---

## 1. Build System

### 1.1 Prerequisites

| Component | Version | Notes |
|-----------|---------|-------|
| GCC/G++ | 7.0+ | Must support C++11 |
| OpenMPI | 3.0+ | Required for multi-rank execution |
| GNU Make | 3.8+ | Build orchestration |
| Python 3 | 3.6+ | Monitor, dashboard, analysis tools |
| matplotlib | 3.x | Plot generation (analysis only) |
| numpy | 1.x | Data processing (analysis only) |

### 1.2 Compile miniMD

```bash
# 1. Navigate to the source directory
cd /path/to/miniMD/ref/

# 2. Copy instrumented source files
cp /path/to/02_src/mpi_comm_version/integrate.cpp .
cp /path/to/02_src/mpi_comm_version/integrate.h .

# 3. Build with OpenMPI support
make openmpi -j 8

# 4. Verify binary
ls -la miniMD_openmpi
# Expected: ~500KB executable
```

### 1.3 Build Targets

| Target | Command | Output |
|--------|---------|--------|
| OpenMPI | `make openmpi -j 8` | `miniMD_openmpi` |
| Serial | `make serial -j 8` | `miniMD_serial` |
| Clean | `make clean` | Removes all build artifacts |

---

## 2. Cluster Deployment (CAC Frontenac)

### 2.1 SLURM Resource Allocation

```bash
# Interactive session (recommended for development/demos)
salloc --nodes=1 \
       --partition=gpu-rgrant \
       --constraint=lkb \
       --ntasks=16 \
       --cpus-per-task=1

# Batch submission
sbatch submit_test_job.sbatch
```

### 2.2 Environment Setup

```bash
# Load required modules (Frontenac-specific)
module load openmpi

# Set shared memory hint path
export PHASE_HINT_PATH=/dev/shm/minimd_phase_hints_myrun.bin

# Link checkpoint directory to local scratch (for I/O phases)
echo $SLURM_TMPDIR
ln -s $SLURM_TMPDIR/chk chk

# Verify the link
ls -l chk
# Expected: chk -> /lscratch/slurm-job-XXXXXXX-1/chk
```

### 2.3 Unified Run Setup (Automated)

```bash
# Use the setup script to create a portable run directory
bash 03_scripts/cluster_jobs/setup_unified_run.sh

# This creates:
# capstone_run/
# ├── miniMD_openmpi
# ├── in.lj.miniMD
# ├── monitor.py
# ├── dvfs_dashboard.py
# ├── bridge_to_dashboard.py
# └── how_to_run.txt
```

---

## 3. Execution Procedures

### 3.1 Three-Terminal Demo (Manual)

#### Terminal 1: Monitor (Core 30)
```bash
export PHASE_HINT_PATH=/dev/shm/minimd_phase_hints_myrun.bin

taskset -c 30 python3 -u ./mon.py \
  --hint-file "$PHASE_HINT_PATH" \
  --freq-low 1200000 \
  --freq-mid 1600000 \
  --poll-ms 2 \
  --low-after-ms 2 \
  --mid-after-ms 5
```

#### Terminal 2: miniMD Application (Cores 4–29)
```bash
export PHASE_HINT_PATH=/dev/shm/minimd_phase_hints_myrun.bin

OMP_NUM_THREADS=1 \
OMP_PROC_BIND=true \
OMP_PLACES=cores \
PHASE_HINT_PATH="$PHASE_HINT_PATH" \
taskset -c 4-29 \
mpirun -np 26 \
  -x PHASE_HINT_PATH \
  --bind-to core \
  --map-by core \
  --report-bindings \
  ./miniMD_openmpi -i in.lj.miniMD
```

#### Terminal 3: Dashboard (Any Core)
```bash
export PHASE_HINT_PATH=/dev/shm/minimd_phase_hints_myrun.bin
python3 dashboard.py --cores 32 --refresh 0.5 --hint-file "$PHASE_HINT_PATH"
```

### 3.2 Automated tmux Demo (`launch_demo.sh`)

```bash
# One-command launch (creates 3-pane tmux session)
bash launch_demo.sh

# Layout:
# ┌─────────────────────────────────────┐
# │ Pane 0: Monitor (mon.py)  [4 lines] │
# ├──────────────────┬──────────────────┤
# │ Pane 1: mpirun   │ Pane 2: Dashboard│
# │ (Cores 4-29)     │ (130 cols wide)  │
# └──────────────────┴──────────────────┘
```

**Execution Order:**
1. Monitor starts first (waits for hint file)
2. Dashboard starts (waits for hint file)
3. `mpirun` starts last (creates hint file → monitor and dashboard attach)

### 3.3 MPI Run Configurations

| Workers | Command Suffix | Core Affinity | Notes |
|---------|---------------|---------------|-------|
| 1 | `-np 1` | `taskset -c 4` | Single rank |
| 2 | `-np 2` | `taskset -c 4-5` | 2 ranks |
| 4 | `-np 4` | `taskset -c 4-7` | 4 ranks |
| 8 | `-np 8` | `taskset -c 4-11` | 8 ranks |
| 16 | `-np 16` | `taskset -c 4-19` | 16 ranks (max power-of-2) |
| 26 | `-np 26` | `taskset -c 4-29` | 26 ranks (typical demo) |
| 30 | `-np 30` | `taskset -c 0-29` | 30 ranks (absolute max) |

### 3.4 CLI Flags (miniMD)

| Flag | Default | Description |
|------|---------|-------------|
| `-i <file>` | `in.lj.miniMD` | Input deck |
| `--comm_phase <0\|1>` | `1` | Enable/disable communication phase |
| `--comm_standin_mb <MB>` | `309` | Stand-in communication data |
| `--comm_chunk_kb <KB>` | `1024` | MPI send/recv chunk size |
| `--ckpt <step>` | `0` | Checkpoint at timestep (Gia's flag) |

---

## 4. Post-Run Operations

### 4.1 Governor Restoration (Critical Safety Step)

If the monitor crashes or is killed mid-actuation, worker cores may be permanently stuck in `userspace` governor at low frequency. **Always run cleanup after unexpected termination:**

```bash
# cleanup.sh — restores all worker cores to performance
for c in {4..29}; do
    echo 'performance' > "/sys/devices/system/cpu/cpu${c}/cpufreq/scaling_governor" 2>/dev/null || true
done
echo "Governors restored."

# Also clean up orphaned shared memory
rm -f /dev/shm/minimd_phase_hints_myrun.bin 2>/dev/null
echo "Shared memory hints cleared."
```

### 4.2 Checkpoint Cleanup

```bash
# Remove old checkpoint files
rm -rf chk/*

# Or remove the symlink entirely
rm -f chk
```

### 4.3 Data Collection

```bash
# Copy results from cluster to local
scp user@frontenac:/path/to/results_*.csv ./05_data/raw_results/

# Generate plots
python3 02_src/analysis/regenerate_all_plots_v4.py
```

---

## 5. Batch Test Execution

### 5.1 Test Matrix

| Test | Script | Controller | Description |
|------|--------|------------|-------------|
| **A** | `batch_test_a.sh` | None | Raw baseline (no monitor) |
| **B** | `batch_test_b.sh` | Monitor only | Monitoring overhead measurement |
| **C** | `batch_test_c.sh` | `comm_freq_controller.py` | Simple phase-detection controller |
| **D** | `batch_test_d.sh` | Extended | Extended test matrix |

### 5.2 Running a Full Test Suite

```bash
# Test B (baseline with monitoring)
bash batch_test_b.sh

# Test C (with frequency controller)
bash batch_test_c.sh

# Compare results
python3 analyze_results.py
```

---

## 6. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Permission denied` writing to cpufreq | Not root / no cpufreq group | `sudo chmod 666 /sys/devices/system/cpu/cpu*/cpufreq/scaling_*` |
| Monitor hangs at "waiting for hint file" | miniMD hasn't started yet | Start miniMD in another terminal |
| Dashboard shows "Waiting for hint file" | Hint file not yet created | Wait for miniMD Rank 0 initialization |
| All cores stuck at 1.2 GHz | Monitor crashed during I/O phase | Run `cleanup.sh` |
| RAPL energy negative | Counter overflow (>80 min) | Correct with modular arithmetic |
| `mpirun` error: "not enough slots" | Too many ranks requested | Add `--oversubscribe` flag |
| Checkpoint directory missing | Symlink not created | `ln -s $SLURM_TMPDIR/chk chk` |
| Dashboard garbled | Terminal too small | Resize to ≥130 columns, ≥40 rows |

---

## 7. Emergency Procedures

### 7.1 Kill All Processes
```bash
# Kill miniMD
pkill -f miniMD_openmpi

# Kill monitor
pkill -f mon.py

# Kill dashboard
pkill -f dashboard.py

# Restore governors
bash cleanup.sh
```

### 7.2 Full Reset
```bash
# Kill tmux session
tmux kill-session -t minimd_demo

# Clean shared memory
rm -f /dev/shm/minimd_phase_hints*.bin

# Restore governors
for c in {0..31}; do
    echo 'performance' > "/sys/devices/system/cpu/cpu${c}/cpufreq/scaling_governor" 2>/dev/null || true
done

# Remove checkpoints
rm -rf chk/* 2>/dev/null
```
