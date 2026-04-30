# MiniMD Performance Analysis: Frequency Scaling Study

## Overview
This report provides a comparative analysis of MiniMD execution times across three CPU frequencies (1.2 GHz, 1.6 GHz, 2.0 GHz) for various MPI rank counts (1, 2, 4, 8, 16, 30). The analysis aims to quantify the trade-offs between performance and potential energy savings for communication-phase optimization.

## Methodology
Data for the 2.0 GHz (maximum hardware frequency) configuration was extracted from high-fidelity empirical hardware logs (`results_manual_test_b.csv`). Performance for 1.2 GHz and 1.6 GHz was modeled using inverse frequency scaling for CPU-bound phases ($T_{force}, T_{neigh}$), while preserving fixed-duration overheads like I/O and setup times, reflecting the established methodology of the research group.

## Execution Time Summary (Seconds)

| MPI Ranks | 1.2 GHz | 1.6 GHz | 2.0 GHz |
| :--- | :--- | :--- | :--- |
| 1 | 801.4 | 612.2 | 498.7 |
| 2 | 420.5 | 325.1 | 267.9 |
| 4 | 224.8 | 177.4 | 149.0 |
| 8 | 129.1 | 105.3 | 91.0 |
| 16 | 90.5 | 76.3 | 67.8 |
| 30 | 64.0 | 56.3 | 51.7 |

## Performance Scaling Visualization

### Execution Time Scaling
The following figure illustrates the strong scaling behavior of MiniMD at different fixed frequencies.

![Execution Time Scaling](file:///c:/Users/Johnnie/Documents/ELEC_498_All_directories_and_branches_folder_for_2026_02_15/06_outputs/02_performance_analysis_sweep/figures/execution_time_scaling.png)

### Frequency-Based Speedup
This figure shows the speedup gained by increasing from 1.2 GHz, normalized against the lowest frequency.

![Frequency Speedup](file:///c:/Users/Johnnie/Documents/ELEC_498_All_directories_and_branches_folder_for_2026_02_15/06_outputs/02_performance_analysis_sweep/figures/frequency_speedup.png)

## Key Conclusions
1.  **CPU-Bound Sensitivity**: MiniMD execution time is highly sensitive to CPU frequency at low rank counts, where the compute phase ($T_{force}$) dominates.
2.  **I/O Ceiling**: As rank counts increase to N=30, the relative benefit of higher frequency diminishes as frequency-independent I/O phases (~32s) begin to dominate the total runtime (constituting ~62% of the runtime at N=30 @ 2.0 GHz).
3.  **Optimal Optimization Target**: The communication phase itself is extremely short (~0.02s), making it a secondary target for energy savings compared to the sustained I/O checkpoints.
