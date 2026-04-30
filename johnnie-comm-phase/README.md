# Johnnie's Communication Phase Optimization for miniMD

## Overview

This directory contains a modified version of miniMD with an additional **communication phase** 
that runs after Gia's I/O checkpoint. The communication phase simulates network data transfer 
by having **only MPI rank 0** send/receive the total checkpoint payload through MPI loopback, 
while all other ranks wait at `MPI_Barrier`.

## Core Layout (32-core node)

```
Core 31:    RESERVED  — HPC maintenance, NO permission to change freq
Core 30:    MONITOR   — Python frequency controller runs here
Cores 0–N:  WORKERS   — MPI processes, 1:1 core-binding

Valid worker counts: 1, 2, 4, 8, 16, 30
  30 = max (core 30 = monitor, core 31 = reserved)
  16 = max power of 2
```

## What was changed

### Modified files (from `gia-scaling-io` base):

| File | Changes |
|------|---------|
| `integrate.h` | Added `comm_phase_enabled`, `comm_standin_bytes`, `comm_chunk_kb` fields |
| `integrate.cpp` | Added `calculate_per_rank_data_bytes()`, `simulate_network_communication()`, phase marker signaling |
| `ljs.cpp` | Added `--comm_phase`, `--comm_standin_mb`, `--comm_chunk_kb` CLI flags |

### New files:

| File | Purpose |
|------|---------|
| `comm_freq_controller.py` | Simple comm-phase frequency controller |
| `integrated_freq_controller.py` | Full controller: Zane's β-adaptation + Johnnie's comm phase |
| `run_freq_tests.sh` | Tests at 1.2/1.6/2.0 GHz with configurable worker counts |
| `verify_file_sizes.py` | Verifies per-rank/total data sizes for all configurations |
| `ON_CLUSTER_TESTING_GUIDE.md` | Step-by-step guide for HPC testing |

## How it works

```
Simulation Loop (first half)
    ↓
I/O Checkpoint Phase (Gia's code)
  → writes phase_marker.txt: "IO_START"
  → all ranks write checkpoint data to disk
  → writes phase_marker.txt: "IO_END"
    ↓
Communication Phase (Johnnie's code)
  → writes phase_marker.txt: "COMM_START <bytes>"
  → rank 0: MPI_Isend/MPI_Recv loopback of total checkpoint data
  → other ranks: wait at MPI_Barrier (idle)
  → writes phase_marker.txt: "COMM_END"
    ↓
Simulation Loop (second half)
  → writes phase_marker.txt: "COMPUTE_RESUME"
```

## Data size calculation

Per-rank checkpoint data:
```
header (96 bytes) + nlocal × 3 × sizeof(MMD_float) × 3 + nlocal × sizeof(int)
= 96 + nlocal × 76 bytes  (when MMD_float = double, 8 bytes)
```

Total communication payload = per-rank data × number of MPI ranks

Stand-in default: **309 MB** (used when runtime calculation is smaller).

## Build

```bash
cp integrate.h integrate.cpp ljs.cpp /path/to/miniMD/
cd /path/to/miniMD
make openmpi -j 8
```

## Run

Replace `N` with your worker count (1, 2, 4, 8, 16, or 30).

### Basic run (communication phase enabled by default):
```bash
mpirun --oversubscribe -np N --bind-to core ./miniMD_openmpi -i in.lj.miniMD
```

### Examples:
```bash
# 8 workers:
mpirun --oversubscribe -np 8 --bind-to core ./miniMD_openmpi -i in.lj.miniMD

# 16 workers:
mpirun --oversubscribe -np 16 --bind-to core ./miniMD_openmpi -i in.lj.miniMD

# 30 workers (max):
mpirun --oversubscribe -np 30 --bind-to core ./miniMD_openmpi -i in.lj.miniMD
```

### With frequency controller (on HPC node, pinned to core 30):
```bash
# Terminal 1: Start controller
taskset -c 30 python3 comm_freq_controller.py --workers N --log freq.csv

# Terminal 2: Run miniMD
mpirun --oversubscribe -np N --bind-to core ./miniMD_openmpi -i in.lj.miniMD
```

### Disable communication phase (baseline):
```bash
mpirun --oversubscribe -np N --bind-to core ./miniMD_openmpi -i in.lj.miniMD --comm_phase 0
```

## CLI Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--comm_phase <0\|1>` | 1 | Enable/disable communication phase |
| `--comm_standin_mb <MB>` | 309 | Stand-in total data in MB |
| `--comm_chunk_kb <KB>` | 1024 | MPI send/recv chunk size in KB |

## Output

During the communication phase, you'll see:
```
========================================
COMMUNICATION PHASE (Rank 0 Only)
========================================
Per-rank data (runtime): X.XX MB
Total data (runtime): X.XX MB [N ranks × per-rank]
Stand-in total: 309.00 MB
...
=== Communication Phase Complete ===
Duration: X.XXX seconds
Effective bandwidth: XXXX.XX MB/s
====================================
```
