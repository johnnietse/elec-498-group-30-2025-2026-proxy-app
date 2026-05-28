# 12_glossary_and_references.md — Glossary, Acronyms, and External References

---

## 1. Glossary of Project Terms

| Term | Definition |
|------|-----------|
| **Phase Hint** | A structured data record written to shared memory by the instrumented application indicating its current computational phase |
| **PhaseSlot** | A 24-byte struct containing sequence number, rank, core, phase code, and timestamp for one MPI rank |
| **PhaseTable** | The top-level shared-memory structure containing a magic number, slot count, and up to 64 `PhaseSlot` entries |
| **Seqlock** | A lock-free synchronization protocol where writers increment a sequence counter (odd = writing, even = stable) and readers retry if the counter changed during their read |
| **Governor** | A Linux `cpufreq` policy that determines how a CPU core selects its operating frequency. Examples: `performance` (always max), `userspace` (manually set), `ondemand` (load-based) |
| **Actuation** | The act of writing a new frequency or governor setting to the Linux sysfs interface to change CPU behavior |
| **Worker Core** | A CPU core assigned to run an MPI rank of the miniMD simulation |
| **Monitor Core** | Core 30 — dedicated to running the Python frequency controller (`mon.py`) |
| **Reserved Core** | Core 31 — owned by the HPC system scheduler and never modified by the project |
| **Phase Marker** | A text-based phase signaling file (`phase_marker.txt`) used as a fallback when shared-memory protocol is not available |
| **Bridge** | `bridge_to_dashboard.py` — a compatibility layer that translates text-based phase markers into shared-memory `PhaseTable` format |
| **Test A** | Baseline experiment — raw miniMD execution with no monitoring or controller |
| **Test B** | Baseline with monitoring — measures the overhead of the monitoring system alone |
| **Test C** | Simple controller — `comm_freq_controller.py` active, lowers frequency during I/O and communication phases |
| **Test C2** | Adaptive controller — `integrated_freq_controller.py` with beta-adaptation; **abandoned** due to excessive overhead |
| **Test D** | Extended test matrix with additional parameter combinations |
| **Checkpoint** | A snapshot of simulation state (positions, velocities, forces) written to disk during the I/O phase |
| **Stand-in Data** | A configurable amount of synthetic data (default 309 MB) used when runtime-calculated data is smaller than the target |
| **MPI Loopback** | Rank 0 sends data to itself (`MPI_Isend` + `MPI_Recv` with destination = 0) to simulate network traffic |
| **Padding Traffic** | Additional MPI send/recv operations after the actual data is transferred, used to sustain the communication phase for a target duration |
| **Sparkline** | A compact inline chart (`▁▂▃▄▅▆▇█`) used in the TUI dashboard to show frequency history |
| **Pareto Frontier** | The set of configurations where no other configuration is better in both energy and performance simultaneously |
| **Energy-Delay Product (EDP)** | A combined metric: `Energy (J) × Time (s)` — lower is better |

---

## 2. Acronym Reference

| Acronym | Expansion |
|---------|-----------|
| **DVFS** | Dynamic Voltage and Frequency Scaling |
| **RAPL** | Running Average Power Limit (Intel power metering) |
| **MPI** | Message Passing Interface |
| **HPC** | High-Performance Computing |
| **CAC** | Centre for Advanced Computing (Queen's University) |
| **SLURM** | Simple Linux Utility for Resource Management (job scheduler) |
| **TUI** | Terminal User Interface |
| **IPC** | Inter-Process Communication |
| **SHM** | Shared Memory |
| **POSIX** | Portable Operating System Interface |
| **LJS** | Lennard-Jones System (miniMD's molecular potential) |
| **NUMA** | Non-Uniform Memory Access |
| **SIMD** | Single Instruction, Multiple Data |
| **EDP** | Energy-Delay Product |
| **ADR** | Architecture Decision Record |
| **CLI** | Command-Line Interface |
| **CSV** | Comma-Separated Values |
| **GPIO** | (Not used — but referenced) General Purpose I/O |
| **PID** | (Controller context) Proportional-Integral-Derivative control |
| **PID** | (OS context) Process Identifier |
| **EPYC** | AMD's server processor brand (used in Frontenac) |
| **OMP** | OpenMP (shared-memory parallelism) |
| **PAD** | Array padding constant in miniMD for cache-line alignment |
| **MD** | Molecular Dynamics |

---

## 3. Phase Code Reference

| Code | Name | Value | Category | Governor Action |
|------|------|-------|----------|-----------------|
| `PHASE_COMPUTE` | Compute | 0 | Active | `performance` (2.0 GHz) |
| `PHASE_COMMUNICATE` | Communicate | 1 | MPI Internal | `userspace` 1.6 GHz (after 5ms) |
| `PHASE_EXCHANGE` | Exchange | 2 | MPI Internal | `userspace` 1.6 GHz (after 5ms) |
| `PHASE_BORDERS` | Borders | 3 | MPI Internal | `userspace` 1.6 GHz (after 5ms) |
| `PHASE_REVERSE` | Reverse | 4 | MPI Internal | `userspace` 1.6 GHz (after 5ms) |
| `PHASE_IO` | I/O | 5 | Low-Value | `userspace` 1.2 GHz (after 2ms) |
| `PHASE_SYNTH_ACTIVE` | Synth Active | 6 | Active | `performance` (2.0 GHz) |
| `PHASE_SYNTH_WAIT` | Synth Wait | 7 | Low-Value | `userspace` 1.2 GHz (after 2ms) |
| `PHASE_DONE` | Done | 8 | Terminal | Cleanup & restore |

---

## 4. Magic Numbers and Constants

| Constant | Value | Location | Purpose |
|----------|-------|----------|---------|
| `PHASE_MAGIC` | `0x50485331` ("PHS1") | integrate.cpp, mon.py, dashboard.py, bridge.py | Validates that shared-memory file contains a valid PhaseTable |
| `MAX_PHASE_SLOTS` | `64` | All shared-memory consumers | Maximum MPI ranks supported |
| `RESERVED_CORE` | `31` | mon.py, dashboard.py | HPC system core — never modify |
| `MONITOR_CORE` | `30` | mon.py, dashboard.py | Monitor process core — never throttle |
| `MAX_MHZ` | `3600.0` | dashboard.py | Maximum frequency for bar chart scaling |
| `DEFAULT_COMM_TARGET_DURATION_SEC` | `30.0` | integrate.cpp | Default target for communication phase duration |
| `DEFAULT_COMM_SLEEP_US` | `0` | integrate.cpp | No sleep between communication chunks |

---

## 5. File Path Constants

| Path | Used By | Purpose |
|------|---------|---------|
| `/dev/shm/minimd_phase_hints.bin` | Default hint file | Lock-free phase communication |
| `/dev/shm/minimd_phase_hints_myrun.bin` | Demo scripts | Isolated hint file for specific runs |
| `/sys/devices/system/cpu/cpuN/cpufreq/scaling_governor` | mon.py | Set CPU frequency governor |
| `/sys/devices/system/cpu/cpuN/cpufreq/scaling_setspeed` | mon.py | Set CPU frequency (userspace only) |
| `/sys/devices/system/cpu/cpuN/cpufreq/scaling_cur_freq` | dashboard.py | Read current CPU frequency |
| `/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj` | monitoring.py | Read RAPL energy counter |
| `/proc/<pid>/io` | monitoring.py | Read per-process I/O statistics |

---

## 6. Hardware Platform Reference

### CAC Frontenac Node (from Blueprint Table 3)

| Specification | Value |
|--------------|-------|
| CPU | AMD EPYC 7551P |
| Cores | 32 (1 socket, 1 thread/core) |
| Base Frequency | 1.2 GHz |
| Max Frequency | 2.0 GHz |
| Memory | 125 GiB |
| NUMA Nodes | 4 |
| Power Monitoring | RAPL domains |
| Available Governors | `performance`, `userspace`, `ondemand`, `conservative` |
| Frequency Steps | 1.2, 1.4, 1.6, 1.8, 2.0 GHz (200 MHz increments) |

---

## 7. External References

| Resource | URL / Reference |
|----------|----------------|
| miniMD | Mantevo Project — https://mantevo.org |
| OpenMPI | https://www.open-mpi.org |
| CAC Frontenac | Queen's University Centre for Advanced Computing |
| Linux cpufreq | https://www.kernel.org/doc/html/latest/admin-guide/pm/cpufreq.html |
| Intel RAPL | Running Average Power Limit — https://www.intel.com/content/www/us/en/developer/articles/technical/software-security-guidance/advisory-guidance/running-average-power-limit-energy-reporting.html |
| Seqlock Algorithm | https://en.wikipedia.org/wiki/Seqlock |
| Velocity-Verlet | Numerical integration for molecular dynamics — Verlet, L. (1967) |
| Lennard-Jones Potential | Intermolecular potential: V(r) = 4ε[(σ/r)¹² − (σ/r)⁶] |
| Amdahl's Law | Speedup limited by serial fraction: S(N) = 1 / (s + (1−s)/N) |
| SLURM | Simple Linux Utility for Resource Management — https://slurm.schedmd.com |

---

## 8. Team Contact Information

| Name | Role | Student ID | NetID |
|------|------|-----------|-------|
| Johnnie Tse | Communication Phase | 20366054 | 22yht |
| Gia Lee | I/O (Storage) Phase | 20231785 | 19jl253 |
| Zane Prance | MPI Communication Controller | 20233463 | 20zdtp |
| Valerie So | I/O Benchmarking | 20291603 | 20wyvs |

**Supervisor:** Dr. Ryan Grant  
**Course:** ELEC 490/498 — Capstone Project  
**Institution:** Queen's University, Kingston, Ontario, Canada
