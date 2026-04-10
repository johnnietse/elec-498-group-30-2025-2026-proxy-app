# 08_test_gui

## Directory Purpose
This directory contains experimental user-facing dashboards designed to monitor the system's performance in real-time.

## Key Contents
- **TUI Dashboard (`dashboard.py`)**: A Terminal User Interface showing real-time metrics of the frequency controller. It visualizes per-core frequency limits, plots temporal sliding windows of the CPU averages, and displays the exact MPI phase hints read straight from `/dev/shm`.

## Usage Notes
This tool is optional and primarily built to satisfy the Capstone Blueprint's Optional Interface requirements. It relies on `curses` and standard terminal rendering buffers and should run in a separate SSH/Tmux session alongside the main experiment.
