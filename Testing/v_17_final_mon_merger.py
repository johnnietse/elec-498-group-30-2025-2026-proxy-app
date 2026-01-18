#!/usr/bin/env python3
"""
INTELLIGENT Communication Phase Monitor for miniMD - Version 17.0
OPTIMIZED for LOW OVERHEAD (<2%) using PERF STREAMING
"""
import sys
import subprocess
import time
import csv
import os
import math
import statistics
import glob
import fcntl
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime
import numpy as np

# ---------------------- CONFIGURATION ----------------------

CMD = ["mpirun", "--oversubscribe", "-np", "32", "./miniMD_openmpi", "i", "in.lj.miniMD"]
LOG_FILE = f"comm_phase_monitor_log.csv"
SUMMARY_FILE = f"comm_phase_summary_log.txt"

# Sample interval
SAMPLE_INTERVAL = 0.2

PERF = "/cvmfs/soft.computecanada.ca/gentoo/2023/x86-64-v3/usr/bin/perf"
RAPL_PATH = "/sys/class/powercap/intel-rapl:0/energy_uj"
RAPL_DRAM_PATH = "/sys/class/powercap/intel-rapl:0:0/energy_uj"

FREQ_MAX = "2000000"
FREQ_MIN = "1600000"

# Thresholds
IPC_THRESHOLD = 1.6
MISS_THRESHOLD = 0.30
POWER_MARGIN_THRESHOLD = 1.5
TICKS_PER_SECOND = 100
THREAD_APP_LIMIT = 0.25
MAX_CTX_RATE = 1e6



# Network interface to monitor
NETWORK_INTERFACES = ["ib0", "ib1", "eth0", "eth1", "eno1", "ens1"]

EMPIRICAL_SCALING_DATA = {
    2: {"comm_pct": 23.7, "compute_pct": 62.5, "force_pct": 62.5, "neigh_pct": 12.6},
    4: {"comm_pct": 40.2, "compute_pct": 47.5, "force_pct": 47.5, "neigh_pct": 11.7},
    8: {"comm_pct": 75.5, "compute_pct": 14.9, "force_pct": 14.9, "neigh_pct": 9.3},
    16: {"comm_pct": 87.5, "compute_pct": 4.6, "force_pct": 4.6, "neigh_pct": 7.7},
    32: {"comm_pct": 96.9, "compute_pct": 1.9, "force_pct": 1.9, "neigh_pct": 0.3},
    64: {"comm_pct": 97.8, "compute_pct": 0.8, "force_pct": 0.8, "neigh_pct": 0.2}
}

# System metric 
class IntelligentPhaseMonitor:
    def