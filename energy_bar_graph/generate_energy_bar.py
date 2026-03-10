#!/usr/bin/env python3
"""
Energy Comparison Bar Graph — All MPI Ranks × Tests B, C, C2
(Test A excluded per user request)

Data from results_manual_test_c2.csv (lines 33937-33970 of test_results file):
  Test B:  N=1(6), N=2(5), N=4(5), N=8(6), N=16(9), N=30(6)
  Test C:  N=16 only (1 trial) — comm_freq_controller.py
  Test C2: N=1(5), N=2(5), N=4(5), N=8(5), N=16(6), N=30(5) — integrated_freq_controller.py
"""
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.rcParams.update({
    'figure.facecolor': 'white',
    'axes.facecolor': '#f8f9fa', 'axes.edgecolor': '#dee2e6',
    'axes.grid': True, 'grid.alpha': 0.3,
    'font.size': 11, 'axes.titlesize': 15, 'axes.labelsize': 13,
    'savefig.bbox': 'tight', 'savefig.dpi': 150,
})

out_dir = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# RAW DATA  — energy in Joules
# ============================================================

# TEST B (comm phase ON, no controller, performance governor)
test_b_energy = {
    1:  [38388.559, 38411.212, 39701.205, 39176.334, 39221.244, 40856.542],
    2:  [25890.750, 22408.144, 22069.030, 22929.904, 26904.075],
    4:  [16711.025, 14333.890, 16777.209, 21698.650, 12828.816],
    8:  [11524.713, 10068.417, 9983.275, 8956.522, 11886.480, 9588.311],
    16: [9032.496, 9813.485, 7412.733, 7418.736, 10392.754,
         6914.451, 6795.201, 6755.405, 8640.529],
    30: [7091.102, 7176.393, 6272.422, 9628.442, 5482.405, 7143.214],
}

# TEST C (comm_freq_controller.py) — only N=16
test_c_energy = {
    16: [11093.842],
}

# TEST C2 (integrated_freq_controller.py) — ALL RANKS
# Parsed from results_manual_test_c2.csv at end of test_results file
# First N=16 entry (12933.609) was from the earlier buggy run; using the 5 clean runs
test_c2_energy = {
    1:  [107029.817, 82287.444, 70144.701, 67510.596, 69413.992],
    2:  [43740.853, 41501.659, 28353.507, 43695.359, 32161.236],
    4:  [18397.632, 23880.601, 40019.592, 21866.314, 20503.661],
    8:  [13232.784, 11764.566, 16083.512, 17429.916, 9386.475],
    16: [9146.940, 8894.617, 9652.344, 9466.112, 7487.059],
    30: [7059.439, 6500.147, 9912.202, 12232.770, 8036.818],
}

ranks = [1, 2, 4, 8, 16, 30]

# Colors
C_B  = '#DD8452'   # Orange — Test B
C_C  = '#55A868'   # Green  — Test C
C_C2 = '#C44E52'   # Red    — Test C2

# ============================================================
# GROUPED BAR CHART
# ============================================================
tests = [
    ('Test B (Comm ON, no ctrl)', test_b_energy, C_B),
    ('Test C (Simple Ctrl)',      test_c_energy,  C_C),
    ('Test C2 (Adaptive Ctrl)',   test_c2_energy, C_C2),
]

n_tests = len(tests)
n_ranks = len(ranks)

fig, ax = plt.subplots(figsize=(16, 8))

x = np.arange(n_ranks)
total_width = 0.72
bar_w = total_width / n_tests

for i, (label, data, color) in enumerate(tests):
    positions = []
    vals = []
    errs = []
    trial_counts = []

    for j, r in enumerate(ranks):
        if r in data:
            positions.append(x[j] + (i - n_tests / 2 + 0.5) * bar_w)
            vals.append(np.mean(data[r]))
            errs.append(np.std(data[r]))
            trial_counts.append(len(data[r]))

    if vals:
        bars = ax.bar(positions, vals, bar_w * 0.88, yerr=errs, capsize=4,
                      color=color, edgecolor='black', linewidth=0.5,
                      label=label, zorder=3, alpha=0.9)

        # Annotate each bar
        for bar, val, err, n in zip(bars, vals, errs, trial_counts):
            y_offset = err + max(max(np.mean(test_b_energy[r]) for r in ranks),
                                  max(np.mean(test_c2_energy[r]) for r in ranks)) * 0.015
            trial_label = f'({n}t)' if n > 1 else '(1t)'
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + y_offset,
                    f'{val:,.0f}J\n{trial_label}',
                    ha='center', va='bottom',
                    fontweight='bold', fontsize=7.5, color='#222222')

ax.set_xticks(x)
ax.set_xticklabels([f'N = {r}' for r in ranks], fontsize=13, fontweight='bold')
ax.set_ylabel('Total Energy (J)', fontsize=14)
ax.set_title('Energy Consumption vs MPI Ranks — Tests B, C, C2',
             fontsize=16, fontweight='bold', pad=15)
ax.legend(loc='upper right', fontsize=11, framealpha=0.95)

# Set y-axis
all_means = ([np.mean(test_b_energy[r]) + np.std(test_b_energy[r]) for r in ranks] +
             [np.mean(test_c2_energy[r]) + np.std(test_c2_energy[r]) for r in ranks])
ax.set_ylim(0, max(all_means) * 1.22)

# Note
ax.annotate(
    'Note: Test C (comm_freq_controller) only tested at N=16.\n'
    'Error bars show ±1σ across multiple trials.',
    xy=(0.02, 0.96), xycoords='axes fraction',
    fontsize=9.5, va='top', ha='left',
    bbox=dict(boxstyle='round,pad=0.4', facecolor='lightyellow',
              edgecolor='gray', alpha=0.9))

plt.tight_layout()
out_path = os.path.join(out_dir, 'energy_comparison_all_ranks.png')
plt.savefig(out_path)
plt.close()

print(f"Saved: {out_path}")
print("\nEnergy Summary (J):")
print(f"  {'Rank':<6} {'Test B (mean±std)':<24} {'Test C':<18} {'Test C2 (mean±std)'}")
print("  " + "-" * 75)
for r in ranks:
    b_m = np.mean(test_b_energy[r])
    b_s = np.std(test_b_energy[r])
    c_str  = f"{np.mean(test_c_energy[r]):,.0f} J (1t)" if r in test_c_energy else "—"
    c2_m = np.mean(test_c2_energy[r])
    c2_s = np.std(test_c2_energy[r])
    print(f"  N={r:<3} {b_m:>10,.0f} ± {b_s:>6,.0f} J    {c_str:<18} {c2_m:>10,.0f} ± {c2_s:>6,.0f} J ({len(test_c2_energy[r])}t)")
