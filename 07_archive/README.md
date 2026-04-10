# 07_archive

## Directory Purpose
This directory contains deprecated prototypes and iterations abandoned during the design phase of the capstone project. 

## Key Contents
- **Beta Algorithm Controllers**: Early tests (like the `integrated_freq_controller.py`) that attempted to infer communication phases directly from `t_comm` and `perf stat` overheads without application hints.
- **Old Data Sweeps**: Data from Test A, Test B, and Test C2, demonstrating the catastrophic overhead (>50% energy increase) of the older integrated controllers.

## Usage Notes
Everything in this folder is maintained strictly for historical and academic validation purposes—proving the iterative, evidence-driven design pivots documented in the final report. **Do not use scripts from this directory in the final operation pipeline.** Wait phases and large binaries (like the ignored 300MB `.bin` checkpoints) are retained here for potential future debugging.
