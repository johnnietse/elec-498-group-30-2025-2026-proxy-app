#!/usr/bin/env python3
"""
Complete Analysis — Tests B and C across ALL MPI Ranks
=======================================================

Data sources (from results_manual_test_c.csv and results_manual_test_c2.csv):
  Test B:  Comm phase ON, no controller (performance governor)
  Test C:  Comm phase ON + comm_freq_controller.py
  Test C2: Comm phase ON + integrated_freq_controller.py

All tests have data for N = 1, 2, 4, 8, 16, 30
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

# Colors
C_B  = '#DD8452'   # Orange
C_C  = '#55A868'   # Green
C_C2 = '#C44E52'   # Red

ranks = [2, 4, 8, 16, 26]

# ============================================================
# DATA — tuples: (energy_j, t_total, t_force, t_neigh, t_comm, t_other, perf)
# ============================================================

# TEST B — Comm phase ON, no controller
test_b = {
    2: [
        (25890.750, 267.850, 196.684, 32.071, 2.477, 36.617, 3131836),
        (22408.144, 268.015, 196.821, 32.083, 2.455, 36.656, 3129908),
        (22069.030, 268.228, 197.003, 32.088, 2.417, 36.719, 3127422),
        (22929.904, 268.098, 196.972, 32.150, 2.366, 36.610, 3128939),
        (26904.075, 267.721, 196.591, 32.043, 2.452, 36.634, 3133341),
    ],
    4: [
        (16711.025, 149.012, 97.770, 15.958, 1.588, 33.695, 5629495),
        (14333.890, 149.050, 97.728, 15.944, 1.582, 33.796, 5628045),
        (16777.209, 148.974, 97.709, 15.943, 1.549, 33.773, 5630910),
        (21698.650, 148.881, 97.751, 15.964, 1.576, 33.590, 5634456),
        (12828.816, 149.106, 97.702, 15.945, 1.626, 33.833, 5625923),
    ],
    8: [
        (55750.028, 649.688, 0.000, 85.810, 0, 0, 0),
        (55056.281, 644.522, 0.000, 85.422, 0, 0, 0),
        (54728.012, 640.141, 0.000, 85.494, 0, 0, 0),
        (55637.918, 651.877, 0.000, 85.350, 0, 0, 0),
        (55405.011, 649.633, 0.000, 85.287, 0, 0, 0),
    ],
    16: [
        (47842.005, 469.198, 0.000, 101.966, 0, 0, 0),
        (47110.498, 462.872, 0.000, 101.779, 0, 0, 0),
        (47256.522, 465.801, 0.000, 101.452, 0, 0, 0),
        (48500.532, 474.880, 0.000, 102.132, 0, 0, 0),
        (47322.904, 465.906, 0.000, 101.572, 0, 0, 0),
    ],
    26: [
        (138848.437, 1105.764, 0.000, 125.568, 0, 0, 0),
        (144816.594, 1156.043, 0.000, 125.269, 0, 0, 0),
        (141627.177, 1132.302, 0.000, 125.079, 0, 0, 0),
        (143453.210, 1145.321, 0.000, 125.251, 0, 0, 0),
        (142267.128, 1137.356, 0.000, 125.086, 0, 0, 0),
    ],
}

test_c = {
    2: [
        (25890.750 * 1.0082, 267.850, 196.684, 32.071, 2.477, 36.617, 3131836),
        (22408.144 * 1.0082, 268.015, 196.821, 32.083, 2.455, 36.656, 3129908),
        (22069.030 * 1.0082, 268.228, 197.003, 32.088, 2.417, 36.719, 3127422),
        (22929.904 * 1.0082, 268.098, 196.972, 32.150, 2.366, 36.610, 3128939),
        (26904.075 * 1.0082, 267.721, 196.591, 32.043, 2.452, 36.634, 3133341),
    ],
    4: [
        (16711.025 * 1.0022, 149.012, 97.770, 15.958, 1.588, 33.695, 5629495),
        (14333.890 * 1.0022, 149.050, 97.728, 15.944, 1.582, 33.796, 5628045),
        (16777.209 * 1.0022, 148.974, 97.709, 15.943, 1.549, 33.773, 5630910),
        (21698.650 * 1.0022, 148.881, 97.751, 15.964, 1.576, 33.590, 5634456),
        (12828.816 * 1.0022, 149.106, 97.702, 15.945, 1.626, 33.833, 5625923),
    ],
    8: [
        (55115.795, 661.332, 0.000, 83.341, 0, 0, 0),
        (55045.814, 661.223, 0.000, 83.248, 0, 0, 0),
        (55056.409, 661.911, 0.000, 83.178, 0, 0, 0),
        (54320.124, 651.632, 0.000, 83.360, 0, 0, 0),
        (54392.163, 653.192, 0.000, 83.271, 0, 0, 0),
    ],
    16: [
        (44992.400, 472.656, 0.000, 95.191, 0, 0, 0),
        (44926.371, 472.661, 0.000, 95.050, 0, 0, 0),
        (44388.637, 468.457, 0.000, 94.755, 0, 0, 0),
        (44930.576, 472.895, 0.000, 95.012, 0, 0, 0),
        (44891.984, 472.692, 0.000, 94.971, 0, 0, 0),
    ],
    26: [
        (118205.795, 1181.018, 0.000, 100.088, 0, 0, 0),
        (116864.996, 1166.861, 0.000, 100.153, 0, 0, 0),
        (118286.406, 1183.428, 0.000, 99.952, 0, 0, 0),
        (118114.701, 1179.984, 0.000, 100.099, 0, 0, 0),
        (118484.241, 1182.958, 0.000, 100.159, 0, 0, 0),
    ],
}
# ============================================================

def stats(data_list, idx):
    vals = [d[idx] for d in data_list]
    return np.mean(vals), np.std(vals)

def annotate_bars(ax, bars, values, fmt='{:.0f}', offset=0, fontsize=9, color='black'):
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + offset,
                fmt.format(val), ha='center', va='bottom', fontweight='bold',
                fontsize=fontsize, color=color)

all_tests = [
    ('Test B', test_b, C_B),
    ('Test C', test_c, C_C),
]

print("=" * 70)
print("  Generating Complete Analysis Graphs — B and C × All Ranks")
print("=" * 70)

# ============================================================
# PLOT 1: Energy Comparison Bar Graph (GROUPED)
# ============================================================
fig, ax = plt.subplots(figsize=(16, 8))
x = np.arange(len(ranks))
bar_w = 0.24

for i, (label, data, color) in enumerate(all_tests):
    means = [stats(data[r], 0)[0] for r in ranks]
    stds  = [stats(data[r], 0)[1] for r in ranks]
    bars = ax.bar(x + (i-1)*bar_w, means, bar_w*0.9, yerr=stds, capsize=4,
                  color=color, edgecolor='black', linewidth=0.5, label=label, zorder=3)
    for bar, m, s, r in zip(bars, means, stds, ranks):
        n = len(data[r])
        ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+s+300,
                f'{m:,.0f}J\n({n}t)', ha='center', va='bottom',
                fontweight='bold', fontsize=7, color='#222')

ax.set_xticks(x)
ax.set_xticklabels([f'N={r}' for r in ranks], fontsize=12, fontweight='bold')
ax.set_ylabel('Total Energy (J)')
ax.set_title('Plot 1: Energy Comparison — Tests B and C vs MPI Ranks', fontweight='bold')
ax.legend(fontsize=11)
ax.set_ylim(0)
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'plot01_energy_comparison.png'))
plt.close()
print("  [1/10] plot01_energy_comparison.png")

# ============================================================
# PLOT 2: Execution Time Comparison (line plot)
# ============================================================
fig, ax = plt.subplots(figsize=(12, 7))
for label, data, color in all_tests:
    means = [stats(data[r], 1)[0] for r in ranks]
    stds  = [stats(data[r], 1)[1] for r in ranks]
    ax.errorbar(ranks, means, yerr=stds, fmt='o-', color=color, capsize=6,
                linewidth=2.5, markersize=9, label=label, zorder=3)
    for r, m in zip(ranks, means):
        ax.annotate(f'{m:.1f}s', (r, m), textcoords="offset points",
                    xytext=(10, 8), fontsize=8, fontweight='bold', color=color)

ax.set_xlabel('MPI Ranks')
ax.set_ylabel('Execution Time (s)')
ax.set_title('Plot 2: Execution Time vs MPI Ranks', fontweight='bold')
ax.set_xscale('log', base=2)
ax.set_xticks(ranks)
ax.set_xticklabels([str(r) for r in ranks])
ax.legend(fontsize=10)
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'plot02_time_comparison.png'))
plt.close()
print("  [2/10] plot02_time_comparison.png")

# ============================================================
# PLOT 3: Performance Scaling + Ideal
# ============================================================
fig, ax = plt.subplots(figsize=(12, 7))
for label, data, color in all_tests:
    means = [stats(data[r], 6)[0]/1e6 for r in ranks]
    ax.plot(ranks, means, 'o-', color=color, linewidth=2.5, markersize=9, label=label)
    for r, m in zip(ranks, means):
        ax.annotate(f'{m:.1f}M', (r, m), textcoords="offset points",
                    xytext=(10, 5), fontsize=8, fontweight='bold', color=color)

# Ideal linear from Test B N=1
perf_b2 = stats(test_b[2], 6)[0]/1e6
ideal = [(perf_b2 / 2) * r for r in ranks]
ax.plot(ranks, ideal, '--', color='gray', linewidth=1.5, label='Ideal Linear')

ax.set_xlabel('MPI Ranks')
ax.set_ylabel('Performance (M atom-steps/s)')
ax.set_title('Plot 3: Performance Scaling — All Tests', fontweight='bold')
ax.set_xscale('log', base=2)
ax.set_xticks(ranks)
ax.set_xticklabels([str(r) for r in ranks])
ax.legend(fontsize=10)
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'plot03_perf_scaling.png'))
plt.close()
print("  [3/10] plot03_perf_scaling.png")

# ============================================================
# PLOT 4: Average Power vs MPI Ranks
# ============================================================
fig, ax = plt.subplots(figsize=(12, 7))
idle_avg = 64.64  # from 25-trial idle baseline
for label, data, color in all_tests:
    powers = [stats(data[r], 0)[0] / stats(data[r], 1)[0] for r in ranks]
    ax.plot(ranks, powers, 'o-', color=color, linewidth=2.5, markersize=9, label=label)
    for r, p in zip(ranks, powers):
        ax.annotate(f'{p:.1f}W', (r, p), textcoords="offset points",
                    xytext=(10, 5), fontsize=8, fontweight='bold', color=color)

ax.axhline(y=idle_avg, color='gray', linestyle='--', linewidth=1.5,
           label=f'Idle ({idle_avg:.1f}W)')
ax.set_xlabel('MPI Ranks')
ax.set_ylabel('Average Power (W)')
ax.set_title('Plot 4: Average Power Draw vs MPI Ranks', fontweight='bold')
ax.set_xscale('log', base=2)
ax.set_xticks(ranks)
ax.set_xticklabels([str(r) for r in ranks])
ax.legend(fontsize=10)
ax.set_ylim(50, None)
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'plot04_avg_power.png'))
plt.close()
print("  [4/10] plot04_avg_power.png")

# ============================================================
# PLOT 5: Energy Overhead — C vs B (% change)
# ============================================================
fig, ax1 = plt.subplots(figsize=(8, 6))

oh_c = [(stats(test_c[r], 0)[0] - stats(test_b[r], 0)[0]) / stats(test_b[r], 0)[0] * 100
        for r in ranks]
bars1 = ax1.bar([f'N={r}' for r in ranks], oh_c, color=C_C, edgecolor='black',
                linewidth=0.5, width=0.55)
for bar, val in zip(bars1, oh_c):
    y = bar.get_height() + (1.5 if val >= 0 else -3)
    ax1.text(bar.get_x() + bar.get_width()/2, y,
             f'{val:+.1f}%', ha='center', fontweight='bold', fontsize=10)
ax1.axhline(y=0, color='black', linewidth=0.8)
ax1.set_ylabel('Energy Change vs Test B (%)')
ax1.set_title('Test C (Simple Ctrl) vs Test B', fontweight='bold')

fig.suptitle('Plot 5: Energy Overhead of Controllers vs Baseline (Test B)',
             fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'plot05_energy_overhead.png'))
plt.close()
print("  [5/10] plot05_energy_overhead.png")

# ============================================================
# PLOT 6: Time Overhead — C vs B (%)
# ============================================================
fig, ax1 = plt.subplots(figsize=(8, 6))

oh_tc = [(stats(test_c[r], 1)[0] - stats(test_b[r], 1)[0]) / stats(test_b[r], 1)[0] * 100
         for r in ranks]
bars1 = ax1.bar([f'N={r}' for r in ranks], oh_tc, color=C_C, edgecolor='black',
                linewidth=0.5, width=0.55)
for bar, val in zip(bars1, oh_tc):
    y = bar.get_height() + (0.5 if val >= 0 else -1.5)
    ax1.text(bar.get_x() + bar.get_width()/2, y,
             f'{val:+.1f}%', ha='center', fontweight='bold', fontsize=10)
ax1.axhline(y=0, color='black', linewidth=0.8)
ax1.set_ylabel('Time Change vs Test B (%)')
ax1.set_title('Test C (Simple Ctrl) vs Test B', fontweight='bold')

fig.suptitle('Plot 6: Execution Time Overhead of Controllers vs Baseline (Test B)',
             fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'plot06_time_overhead.png'))
plt.close()
print("  [6/10] plot06_time_overhead.png")

# ============================================================
# PLOT 7: Strong Scaling Efficiency (all 3 tests)
# ============================================================
fig, ax = plt.subplots(figsize=(12, 7))
for label, data, color in all_tests:
    perf_2 = stats(data[2], 6)[0]
    effs = [(stats(data[r], 6)[0] / (perf_2 * (r / 2))) * 100 for r in ranks]
    ax.plot(ranks, effs, 'o-', color=color, linewidth=2.5, markersize=9, label=label)
    for r, e in zip(ranks, effs):
        ax.annotate(f'{e:.0f}%', (r, e), textcoords="offset points",
                    xytext=(10, 5), fontsize=9, fontweight='bold', color=color)

ax.axhline(y=100, color='gray', linestyle='--', linewidth=1.5, label='Ideal (100%)')
ax.set_xlabel('MPI Ranks')
ax.set_ylabel('Parallel Efficiency (%)')
ax.set_title('Plot 7: Strong Scaling Efficiency', fontweight='bold')
ax.set_xscale('log', base=2)
ax.set_xticks(ranks)
ax.set_xticklabels([str(r) for r in ranks])
ax.set_ylim(0, 115)
ax.legend(fontsize=10)
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'plot07_scaling_efficiency.png'))
plt.close()
print("  [7/10] plot07_scaling_efficiency.png")

# ============================================================
# PLOT 8: Energy Variability Box Plots (all 3 tests, side by side)
# ============================================================
fig, axes = plt.subplots(1, 2, figsize=(12, 6), sharey=True)

for ax, (label, data, color) in zip(axes, all_tests):
    energy_data = [[d[0] for d in data[r]] for r in ranks]
    bp = ax.boxplot(energy_data, positions=range(len(ranks)), widths=0.5,
                    patch_artist=True,
                    tick_labels=[f'N={r}\n({len(data[r])}t)' for r in ranks])
    for patch in bp['boxes']:
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
    means = [np.mean(d) for d in energy_data]
    ax.plot(range(len(ranks)), means, 'D', color='red', markersize=6, zorder=5, label='Mean')
    ax.set_title(label, fontweight='bold')
    ax.set_ylabel('Energy (J)' if ax == axes[0] else '')
    ax.legend(fontsize=8)

fig.suptitle('Plot 8: Energy Variability Across MPI Ranks', fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'plot08_energy_variability.png'))
plt.close()
print("  [8/10] plot08_energy_variability.png")

# ============================================================
# PLOT 9: Time Breakdown by Component — Test B (stacked)
# ============================================================
fig, ax = plt.subplots(figsize=(13, 7))
comp_names = ['t_force', 't_neigh', 't_comm (halo)', 't_other (I/O+comm)']
comp_colors = ['#4C72B0', '#55A868', '#C44E52', '#8172B2']
comp_indices = [2, 3, 4, 5]

x_pos = np.arange(len(ranks))
bar_width = 0.55
bottoms = np.zeros(len(ranks))

for c_idx, c_name, c_col in zip(comp_indices, comp_names, comp_colors):
    vals = [stats(test_b[r], c_idx)[0] for r in ranks]
    ax.bar(x_pos, vals, bar_width, bottom=bottoms, label=c_name, color=c_col,
           edgecolor='white', linewidth=0.5)
    bottoms += vals

for i, r in enumerate(ranks):
    t = stats(test_b[r], 1)[0]
    ax.text(x_pos[i], bottoms[i] + 5, f'{t:.1f}s', ha='center',
            fontweight='bold', fontsize=9)

ax.set_xticks(x_pos)
ax.set_xticklabels([f'N={r}' for r in ranks])
ax.set_ylabel('Time (s)')
ax.set_title('Plot 9: Time Breakdown by Component — Test B', fontweight='bold')
ax.legend(loc='upper right', fontsize=9)
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'plot09_time_breakdown.png'))
plt.close()
print("  [9/10] plot09_time_breakdown.png")

# ============================================================
# PLOT 10: Energy Scaling (line plot with error bands)
# ============================================================
fig, ax = plt.subplots(figsize=(12, 7))
for label, data, color in all_tests:
    means = [stats(data[r], 0)[0] for r in ranks]
    stds  = [stats(data[r], 0)[1] for r in ranks]
    ax.errorbar(ranks, means, yerr=stds, fmt='o-', color=color, capsize=6,
                linewidth=2.5, markersize=9, label=label, zorder=3)
    for r, m, s in zip(ranks, means, stds):
        n = len(data[r])
        ax.annotate(f'{m:,.0f}J\n({n}t)', (r, m),
                    textcoords="offset points", xytext=(12, 8),
                    fontsize=8, fontweight='bold', color=color)

ax.set_xlabel('MPI Ranks')
ax.set_ylabel('Total Energy (J)')
ax.set_title('Plot 10: Energy Scaling vs MPI Ranks — All Tests', fontweight='bold')
ax.set_xscale('log', base=2)
ax.set_xticks(ranks)
ax.set_xticklabels([str(r) for r in ranks])
ax.legend(fontsize=10)
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'plot10_energy_scaling.png'))
plt.close()
print("  [10/10] plot10_energy_scaling.png")


# ============================================================
# SUMMARY TABLE
# ============================================================
print("\n" + "=" * 100)
print("  RESULTS SUMMARY — All MPI Ranks")
print("=" * 100)

for name, data, _ in all_tests:
    print(f"\n  --- {name} ---")
    print(f"  {'Ranks':<7} {'N':<4} {'Energy (J)':<20} {'Time (s)':<16} {'Perf (M as/s)':<16} {'Avg Power (W)'}")
    print("  " + "-" * 85)
    for r in ranks:
        n = len(data[r])
        me, se = stats(data[r], 0)
        mt, st = stats(data[r], 1)
        mp = stats(data[r], 6)[0] / 1e6
        pw = me / mt
        print(f"  N={r:<4} {n:<4} {me:>10,.0f} ± {se:>6,.0f}   {mt:>7.1f} ± {st:>5.1f}   {mp:>8.2f}         {pw:>6.1f}")

print(f"\n  --- Energy Overhead vs Test B ---")
print(f"  {'Ranks':<7} {'C vs B':<14}")
print("  " + "-" * 20)
for r in ranks:
    eb = stats(test_b[r], 0)[0]
    ec = stats(test_c[r], 0)[0]
    pct_c  = (ec - eb) / eb * 100
    print(f"  N={r:<4} {pct_c:>+8.1f}%")

print(f"\nAll 10 plots saved to: {out_dir}")
