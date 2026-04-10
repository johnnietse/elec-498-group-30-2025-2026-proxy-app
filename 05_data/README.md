# 05_data

## Directory Purpose
This directory is the raw telemetry dump zone. It stores unprocessed log files and raw outputs straight from the hardware measurement controllers.

## Key Contents
- **Raw CSV Output Files**: Aggregated metrics outputted by the bash/Python execution wrappers at runtime.
- **Hardware Telemetry Data**: Raw parses of `perf stat` logs (including `energy-pkg` and `cpu-cycles`) and the recorded baseline execution times.
- **Sweep Dumps**: Frequency, rank string, and energy data mapped from large-scale batch runs (e.g., configurations ranging from N=1 to N=26).

## Usage Notes
Files in this folder should be considered immutable. Data processing scripts (stored in `06_outputs`) should *read* from here but never overwrite. If an experiment is corrupted, manually delete its run log rather than attempting to edit the data points directly.
