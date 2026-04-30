#!/usr/bin/env python3
"""
Energy Comparison Bar Graph — All MPI Ranks × All Tests (A, B, C, C2)
One figure, grouped bars.

Data availability:
  Test A:  N=1 (5 trials), N=16 (1 trial)
  Test B:  N=1 (6), N=2 (5), N=4 (5), N=8 (6), N=16 (9), N=30 (6)
  Test C:  N=16 (1 trial)
  Test C2: N=16 (1 trial)
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
    'font.size': 11, 'axes.titlesize': 14, 'axes.labelsize': 12,
    'savefig.bbox': 'tight', 'savefig.dpi': 150,
})

out_dir = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# DATA — (energy_j, t_total, t_force, t_neigh, t_comm, t_other, perf)
# ============================================================
test_a = {
    1:  [(39609.811,), (45907.620,), (41897.955,), (42780.254,), (40575.270,)],
    16: [(7299.031,)],
}

test_b = {
    1:  [(38388.559,), (38411.212,), (39701.205,), (39176.334,), (39221.244,), (40856.542,)],
    2:  [(25890.750,), (22408.144,), (22069.030,), (22929.904,), (26904.075,)],
    4:  [(16711.025,), (14333.890,), (16777.209,), (21698.650,), (12828.816,)],
    8:  [(11524.713,), (10068.417,), (9983.275,), (8956.522,), (11886.480,), (9588.311,)],
    16: [(9032.496,), (9813.485,), (7412.733,), (7418.736,), (10392.754,),
         (6914.451,), (6795.201,), (6755.405,), (8640.529,)],
    30: [(7091.102,), (7176.393,), (6272.422,), (9628.442,), (5482.405,), (7143.214,)],
}

test_c = {
    16: [(11093.842,)],
}

test_c2 = {
    16: [(12933.609,)],
}

ranks = [1, 2, 4, 8, 16, 30]
tests = {
    'Test A\n(Baseline)':     (test_a, '#4C72B0'),
    'Test B\n(Comm ON)':      (test_b, '#DD8452'),
    'Test C\n(Simple Ctrl)':  (test_c, '#55A868'),
    'Test C2\n(Adaptive)':    (test_c2, '#C44E52'),
}
test_names = list(tests.keys())
n_tests = len(test_names)
n_ranks = len(ranks)

# Compute means and stds
means = {}  # means[(test_name, rank)] = mean energy
stds  = {}
for tname, (tdata, _) in tests.items():
    for r in ranks:
        if r in tdata:
            vals = [d[0] for d in tdata[r]]
            means[(tname, r)] = np.mean(vals)
            stds[(tname, r)]  = np.std(vals)

# ============================================================
# GROUPED BAR CHART
# ============================================================
fig, ax = plt.subplots(figsize=(16, 8))

x = np.arange(n_ranks)
total_width = 0.75
bar_w = total_width / n_tests

for i, tname in enumerate(test_names):
    _, color = tests[tname]
    vals = []
    errs = []
    positions = []
    for j, r in enumerate(ranks):
        if (tname, r) in means:
            vals.append(means[(tname, r)])
            errs.append(stds[(tname, r)])
            positions.append(x[j] + (i - n_tests/2 + 0.5) * bar_w)

    if vals:
        bars = ax.bar(positions, vals, bar_w * 0.9, yerr=errs, capsize=3,
                      color=color, edgecolor='black', linewidth=0.4,
                      label=tname.replace('\n', ' '), zorder=3)
        # Annotate each bar
        for bar, val, err in zip(bars, vals, errs):
            ypos = bar.get_height() + err + 200
            # Use smaller font for very tall bars (N=1)
            fs = 7.5 if val > 15000 else 8.5
            ax.text(bar.get_x() + bar.get_width()/2, ypos,
                    f'{val:,.0f}J', ha='center', va='bottom',
                    fontweight='bold', fontsize=fs, color='#333333',
                    rotation=0)

ax.set_xticks(x)
ax.set_xticklabels([f'N = {r}' for r in ranks], fontsize=12, fontweight='bold')
ax.set_ylabel('Total Energy (J)', fontsize=13)
ax.set_title('Energy Comparison Across All MPI Ranks and Test Configurations',
             fontsize=15, fontweight='bold', pad=15)
ax.legend(loc='upper right', fontsize=10, framealpha=0.9, ncol=2)
ax.set_ylim(0, max(means.values()) * 1.18)

# Add note about missing data
ax.annotate('Note: Test A has data only for N=1 and N=16.\n'
            'Tests C and C2 have data only for N=16.',
            xy=(0.02, 0.97), xycoords='axes fraction',
            fontsize=9, va='top', ha='left',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='lightyellow',
                      edgecolor='gray', alpha=0.9))

plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'energy_comparison_all_ranks.png'))
plt.close()
print(f"Saved: {os.path.join(out_dir, 'energy_comparison_all_ranks.png')}")

# Also print a summary table
print("\nEnergy Summary (J):")
print(f"  {'Rank':<6}", end='')
for tname in test_names:
    print(f"  {tname.replace(chr(10),' '):<22}", end='')
print()
print("  " + "-" * 100)
for r in ranks:
    print(f"  N={r:<3}", end='')
    for tname in test_names:
        if (tname, r) in means:
            m = means[(tname, r)]
            s = stds[(tname, r)]
            n = len(tests[tname][0].get(r, []))
            print(f"  {m:>10,.0f} ±{s:>6,.0f} ({n}t)", end='')
        else:
            print(f"  {'—':>22}", end='')
    print()
