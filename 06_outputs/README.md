# 06_outputs

## Directory Purpose
This directory contains the compiled analytics, data processing scripts, and the final generated visual assets.

## Key Contents
- **`figures/`**: Annotated scatter plots, bar charts, and graphs demonstrating energy efficiency scaling, runtime overheads, and the Power-Performance Pareto Trade-off.
- **`generate_plots.py` / `generate_sweep_report.py`**: Python processing scripts that read raw outputs from `05_data/`, execute the performance models (e.g. Amdahl bounding), and render the final png graphics using matplotlib.
- **Markdown Tables**: Parsed comparative execution data rendered as Markdown tables for easy inclusion into the final team reports.

## Usage Notes
This folder is fully reproducible. If you update the plotting scripts, simply run them and the new graphs and tables will overwrite the old ones.
