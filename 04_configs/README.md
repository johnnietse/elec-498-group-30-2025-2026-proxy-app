# 04_configs

## Directory Purpose
This directory centralizes all parameter definitions, scaling thresholds, compiler flags, and job submission setups used to deploy the application on the cluster.

## Key Contents
- **SLURM Job Templates**: Shell templates detailing node reservations, wall-times, and core placements for the HPC scheduler.
- **Environment Imports**: Definitions for `LD_LIBRARY_PATH`, OpenMPI flags (`--bind-to core`, `--map-by core`), and necessary Python virtual environments.
- **Controller Configuration Files**: Parameter files storing the persistence thresholds (e.g. 2ms, 5ms) and the exact frequencies to switch to (1.2 GHz, 1.6 GHz).

## Usage Notes
When taking this project to a different hardware cluster/node, this is the primary location you must edit. Hardcoded core counts, NUMA node layouts, and expected baseline frequencies are stored here.
