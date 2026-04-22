# miniMD Phase-Aware DVFS Optimization
**Sustainable Supercomputing Using Power Controls to Maximize Performance and Minimize Energy Usage**

**ELEC 490/498 Final Project – Group 30**
- Johnnie Tse (22yht, 20366054)
- Gia Lee (19jl253, 20231785)
- Zane Prance (20zdtp, 20233463)
- Valerie So (20wyvs, 20291603)

## Project Overview
This repository contains the source code, analysis scripts, data logs, and documentation for a user-level, phase-aware Dynamic Voltage and Frequency Scaling (DVFS) controller built for the *miniMD* proxy application. 

The system leverages shared memory phase hints published directly from the application and tracked by a lightweight Python monitor to reduce energy consumption without compromising system stability or requiring node-level privileged access.

## Repository Structure
This workspace uses a professional, corporate-level directory structure to ensure maintainability and readability:

| Directory | Purpose |
|---|---|
| 📁 `02_src/` | Modified C++ source code for miniMD (instrumented with phase hints). |
| 📁 `03_scripts/` | Execution pipelines, controllers (`comm_freq_controller.py`), and SLURM orchestration. |
| 📁 `04_configs/` | Parameter definitions and build environment setups. |
| 📁 `05_data/` | Raw telemetry dumps and RAPL energy logs from hardware trials. |
| 📁 `06_outputs/` | Parse results, analytics, and generated visualizations (graphs/tables). |
| 📁 `07_archive/` | Deprecated prototype tests and historical iterations. |
| 📁 `08_test_gui/` | Real-time TUI dashboard for observing frequency actuation. |

## Quick Start
1. To review the final project results, see **`01_docs/`** and **`06_outputs/`**.
2. To inspect the core frequency governor logic, see **`03_scripts/comm_freq_controller.py`**.
3. To view exactly how phase publishing was added to the simulation, see **`02_src/miniMD/ref/integrate.cpp`**.
