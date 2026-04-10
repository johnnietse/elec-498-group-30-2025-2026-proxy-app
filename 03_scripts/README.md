# 03_scripts

## Directory Purpose
This directory manages the operational runtime and infrastructure of the project, executing the compiled application and controlling the CPU state.

## Key Contents
- **`comm_freq_controller.py`**: The core Phase-Aware Python monitor. Runs on a dedicated core, reads the `/dev/shm` hints via a lock-free protocol, and pushes appropriate CPU frequency changes to the `cpufreq` sysfs interface.
- **Bash Execution Wrappers**: Scripts designed to orchestrate the environment, assign core affinities, start/stop the monitor, and safely restore governor statuses after unexpected crashes.

## Usage Notes
Ensure that the bash execution script and the Python controller are pointing to the exact same shared memory magic numbers / `/dev/shm` paths used in the compiled C++ code.
