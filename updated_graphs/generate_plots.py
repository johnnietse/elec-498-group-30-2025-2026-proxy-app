#!/usr/bin/env python3
"""
Complete Analysis of Manual Test Results — March 9, 2026
Data from: test_results_from_running_manual_commands_guide.txt + terminal logs

Tests:
  A  = Baseline (performance governor, comm phase OFF)
  B  = Comm phase ON, no controller (performance governor)
  C  = Comm phase ON + comm_freq_controller.py       (simple controller)
  C2 = Comm phase ON + integrated_freq_controller.py (adaptive controller)

Hardware: AMD EPYC 7551P 32-Core Processor
  Available frequencies: 2000, 1600, 1200 MHz
  Max hardware frequency: 2000 MHz (requesting 2400 gets clamped to 2000)

Data available:
  Test A: N=1 (5 trials), N=16 (1 trial)
  Test B: N=1 (6 trials), N=2 (5), N=4 (5), N=8 (6), N=16 (9), N=30 (6)
  Test C: N=16 (1 trial)   — comm_freq_controller.py
  Test C2: N=16 (1 trial)  — integrated_freq_controller.py
"""
import os
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import matplotlib.ticker as mticker

plt.rcParams.update({
    'figure.figsize': (10, 6), 'figure.facecolor': 'white',
    'axes.facecolor': '#f8f9fa', 'axes.edgecolor': '#dee2e6',
    'axes.grid': True, 'grid.alpha': 0.3,
    'font.size': 11, 'axes.titlesize': 13, 'axes.labelsize': 12,
    'savefig.bbox': 'tight', 'savefig.dpi': 150,
})

out_dir = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# COLOR PALETTE
# ============================================================
C_A  = '#4C72B0'   # Blue   — Test A
C_B  = '#DD8452'   # Orange — Test B
C_C  = '#55A868'   # Green  — Test C
C_C2 = '#C44E52'   # Red    — Test C2

# ============================================================
# IDLE BASELINE — 25 trials, 10s each
# ============================================================
idle_power_W = [
    64.63, 64.62, 64.75, 64.64, 64.69, 64.69, 64.64, 64.64, 64.63, 64.63,
    64.64, 64.61, 64.71, 64.61, 64.63, 64.61, 64.62, 64.62, 64.57, 64.61,
    64.63, 64.61, 64.55, 64.62, 64.68
]
idle_avg = np.mean(idle_power_W)
idle_std = np.std(idle_power_W)

# ============================================================
# DATA FORMAT: (energy_j, t_total, t_force, t_neigh, t_comm, t_other, perf)
# ============================================================

# TEST A — Baseline (comm phase OFF, performance governor)
test_a = {
    1: [
        (39609.811, 498.682, 390.263, 63.928, 2.763, 41.727, 1682157),
        (45907.620, 498.749, 390.408, 63.885, 2.720, 41.735, 1681931),
        (41897.955, 498.697, 390.259, 63.896, 2.759, 41.782, 1682104),
        (42780.254, 498.674, 390.291, 63.889, 2.732, 41.762, 1682181),
        (40575.270, 498.403, 390.165, 63.832, 2.691, 41.716, 1683096),
        # trial 6: 2420 J — RAPL counter wraparound, excluded
    ],
    16: [
        (7299.031, 67.887, 29.394, 4.756, 0.797, 32.940, 12356683),
    ],
}

# TEST B — Comm phase ON, no controller (performance governor)
# Using second (clean) batch for N=16
test_b = {
    1: [
        (38388.559, 498.873, 390.184, 63.854, 2.719, 42.116, 1681511),
        (38411.212, 498.665, 390.215, 63.861, 2.726, 41.863, 1682213),
        (39701.205, 498.580, 390.152, 63.853, 2.715, 41.860, 1682499),
        (39176.334, 498.880, 390.387, 63.899, 2.764, 41.831, 1681489),
        (39221.244, 498.598, 390.191, 63.834, 2.740, 41.832, 1682441),
        (40856.542, 498.738, 390.244, 63.907, 2.731, 41.857, 1681967),
    ],
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
        (11524.713, 91.397, 49.186, 7.974, 1.047, 33.191, 9178195),
        (10068.417, 91.474, 49.160, 7.963, 1.042, 33.309, 9170494),
        (9983.275,  91.570, 49.318, 7.972, 1.074, 33.207, 9160857),
        (8956.522,  90.263, 49.179, 7.969, 1.079, 32.036, 9293509),
        (11886.480, 90.190, 49.111, 7.965, 1.105, 32.009, 9301018),
        (9588.311,  91.153, 49.140, 8.038, 1.056, 32.919, 9202748),
    ],
    16: [
        (9032.496,  68.176, 29.400, 4.755, 0.862, 33.160, 12304255),
        (9813.485,  67.925, 29.401, 4.749, 0.798, 32.977, 12349778),
        (7412.733,  68.005, 29.386, 4.738, 0.840, 33.042, 12335282),
        (7418.736,  67.184, 29.380, 4.738, 0.812, 32.255, 12485959),
        (10392.754, 67.894, 29.367, 4.740, 0.806, 32.981, 12355525),
        (6914.451,  67.201, 29.375, 4.733, 0.800, 32.293, 12482894),
        (6795.201,  67.864, 29.370, 4.745, 0.796, 32.953, 12360943),
        (6755.405,  67.865, 29.359, 4.740, 0.829, 32.937, 12360798),
        (8640.529,  67.914, 29.369, 4.739, 0.834, 32.973, 12351748),
    ],
    30: [
        (7091.102, 51.541, 15.947, 2.502, 0.960, 32.132, 16275698),
        (7176.393, 51.780, 15.928, 2.516, 0.984, 32.353, 16200397),
        (6272.422, 51.860, 15.957, 2.502, 0.925, 32.476, 16175482),
        (9628.442, 51.637, 15.952, 2.503, 0.945, 32.237, 16245319),
        (5482.405, 51.768, 15.942, 2.500, 1.032, 32.294, 16204220),
        (7143.214, 51.690, 15.956, 2.507, 1.050, 32.178, 16228813),
    ],
}

# TEST C — comm_freq_controller.py (N=16 only, corrected with 2400 MHz freqs)
test_c = {
    16: [
        (11093.842, 68.218, 29.405, 4.761, 0.844, 33.208, 12296807),
    ],
}

# TEST C2 — integrated_freq_controller.py (N=16 only)
test_c2 = {
    16: [
        (12933.609, 106.763, 45.000, 7.889, 20.511, 33.363, 7857247),
    ],
}

# Controller log details
ctrl_c_log = {
    'freqs': '2400/1600/1200 MHz',
    'transitions': 3,
    'io_duration': 31.949,
    'comm_duration': 0.051,
    'io_freq': '1200 MHz',
    'comm_core0_freq': '2400 MHz',
    'comm_others_freq': '1200 MHz',
    'compute_freq': '2400 MHz',
}
ctrl_c2_log = {
    'freqs': '2400/1600/1200 MHz',
    'transitions': 3,
    'io_duration': 31.449,
    'comm_duration': 0.050,
    'io_freq': '1200 MHz (all)',
    'comm_core0_freq': '2400 MHz',
    'comm_others_freq': '1200 MHz',
    'compute_freq': '2400 MHz (beta-adaptation)',
}


# ============================================================
# HELPERS
# ============================================================
def stats(data_list, idx):
    vals = [d[idx] for d in data_list]
    return np.mean(vals), np.std(vals)

def annotate_bars(ax, bars, values, fmt='{:.0f}', offset=0, fontsize=10, color='black'):
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + offset,
                fmt.format(val), ha='center', va='bottom', fontweight='bold',
                fontsize=fontsize, color=color)

ranks_b = sorted(test_b.keys())  # [1, 2, 4, 8, 16, 30]

print("=" * 70)
print("  Generating Updated Graphs — All MPI Ranks")
print("=" * 70)

# ============================================================
# PLOT 1: Energy Scaling vs MPI Ranks (Test A + Test B overlay)
# ============================================================
fig, ax = plt.subplots(figsize=(11, 6))

# Test B — all ranks
mean_e_b = [stats(test_b[r], 0)[0] for r in ranks_b]
std_e_b  = [stats(test_b[r], 0)[1] for r in ranks_b]
ax.errorbar(ranks_b, mean_e_b, yerr=std_e_b, fmt='o-', color=C_B,
            capsize=6, linewidth=2.5, markersize=9, label='Test B (Comm ON, no ctrl)',
            zorder=3)
for r, e, s in zip(ranks_b, mean_e_b, std_e_b):
    ax.annotate(f'{e:,.0f}J\n({len(test_b[r])} trials)', (r, e),
                textcoords="offset points", xytext=(12, 8), fontsize=8.5,
                fontweight='bold', color=C_B)

# Test A — only N=1, N=16
ranks_a = sorted(test_a.keys())
mean_e_a = [stats(test_a[r], 0)[0] for r in ranks_a]
std_e_a  = [stats(test_a[r], 0)[1] for r in ranks_a]
ax.errorbar(ranks_a, mean_e_a, yerr=std_e_a, fmt='s--', color=C_A,
            capsize=6, linewidth=2, markersize=9, label='Test A (Baseline, no comm)',
            zorder=3)
for r, e in zip(ranks_a, mean_e_a):
    ax.annotate(f'{e:,.0f}J', (r, e), textcoords="offset points",
                xytext=(-15, -20), fontsize=8.5, fontweight='bold', color=C_A)

# Test C and C2 at N=16
e_c  = stats(test_c[16], 0)[0]
e_c2 = stats(test_c2[16], 0)[0]
ax.plot(16, e_c, 'D', color=C_C, markersize=11, zorder=4, label='Test C (Simple Ctrl)')
ax.plot(16, e_c2, 'X', color=C_C2, markersize=11, zorder=4, label='Test C2 (Adaptive Ctrl)')
ax.annotate(f'C: {e_c:,.0f}J', (16, e_c), textcoords="offset points",
            xytext=(15, -15), fontsize=8.5, fontweight='bold', color=C_C)
ax.annotate(f'C2: {e_c2:,.0f}J', (16, e_c2), textcoords="offset points",
            xytext=(15, 5), fontsize=8.5, fontweight='bold', color=C_C2)

ax.set_xlabel('MPI Ranks')
ax.set_ylabel('Total Energy (J)')
ax.set_title('Plot 1: Total Energy vs MPI Ranks')
ax.set_xscale('log', base=2)
ax.set_xticks(ranks_b)
ax.set_xticklabels([str(r) for r in ranks_b])
ax.legend(loc='upper right', fontsize=9)
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'plot01_energy_vs_ranks.png'))
plt.close()
print("  [1/14] plot01_energy_vs_ranks.png")

# ============================================================
# PLOT 2: Execution Time vs MPI Ranks (Test A + Test B)
# ============================================================
fig, ax = plt.subplots(figsize=(11, 6))

mean_t_b = [stats(test_b[r], 1)[0] for r in ranks_b]
std_t_b  = [stats(test_b[r], 1)[1] for r in ranks_b]
ax.errorbar(ranks_b, mean_t_b, yerr=std_t_b, fmt='o-', color=C_B,
            capsize=6, linewidth=2.5, markersize=9, label='Test B', zorder=3)
for r, t in zip(ranks_b, mean_t_b):
    ax.annotate(f'{t:.1f}s', (r, t), textcoords="offset points",
                xytext=(12, 8), fontsize=9, fontweight='bold', color=C_B)

mean_t_a = [stats(test_a[r], 1)[0] for r in ranks_a]
ax.errorbar(ranks_a, mean_t_a, yerr=[stats(test_a[r], 1)[1] for r in ranks_a],
            fmt='s--', color=C_A, capsize=6, linewidth=2, markersize=9,
            label='Test A', zorder=3)
for r, t in zip(ranks_a, mean_t_a):
    ax.annotate(f'{t:.1f}s', (r, t), textcoords="offset points",
                xytext=(-15, -18), fontsize=9, fontweight='bold', color=C_A)

# C/C2 at N=16
t_c  = stats(test_c[16], 1)[0]
t_c2 = stats(test_c2[16], 1)[0]
ax.plot(16, t_c, 'D', color=C_C, markersize=11, zorder=4, label=f'Test C ({t_c:.1f}s)')
ax.plot(16, t_c2, 'X', color=C_C2, markersize=11, zorder=4, label=f'Test C2 ({t_c2:.1f}s)')

ax.set_xlabel('MPI Ranks')
ax.set_ylabel('Execution Time (s)')
ax.set_title('Plot 2: Execution Time vs MPI Ranks')
ax.set_xscale('log', base=2)
ax.set_xticks(ranks_b)
ax.set_xticklabels([str(r) for r in ranks_b])
ax.legend(loc='upper right', fontsize=9)
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'plot02_time_vs_ranks.png'))
plt.close()
print("  [2/14] plot02_time_vs_ranks.png")

# ============================================================
# PLOT 3: Performance Scaling + Ideal Linear (Test B)
# ============================================================
fig, ax = plt.subplots(figsize=(10, 6))
mean_perf_b = [stats(test_b[r], 6)[0] / 1e6 for r in ranks_b]
ideal_perf  = [mean_perf_b[0] * r for r in ranks_b]

ax.plot(ranks_b, mean_perf_b, 'o-', color=C_B, linewidth=2.5, markersize=9,
        label='Actual Performance (Test B)')
ax.plot(ranks_b, ideal_perf, '--', color='gray', linewidth=1.5,
        label='Ideal Linear Scaling')
for r, p in zip(ranks_b, mean_perf_b):
    eff = p / (mean_perf_b[0] * r) * 100 if r > 1 else 100
    ax.annotate(f'{p:.1f}M\n({eff:.0f}%)', (r, p),
                textcoords="offset points", xytext=(12, -5), fontsize=9,
                fontweight='bold', color=C_B)

ax.set_xlabel('MPI Ranks')
ax.set_ylabel('Performance (M atom-steps/s)')
ax.set_title('Plot 3: Strong Scaling — Performance vs MPI Ranks (Test B)')
ax.set_xscale('log', base=2)
ax.set_xticks(ranks_b)
ax.set_xticklabels([str(r) for r in ranks_b])
ax.legend(fontsize=10)
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'plot03_perf_scaling.png'))
plt.close()
print("  [3/14] plot03_perf_scaling.png")

# ============================================================
# PLOT 4: Average Power vs MPI Ranks (Test B)
# ============================================================
fig, ax = plt.subplots(figsize=(10, 6))
mean_power_b = [stats(test_b[r], 0)[0] / stats(test_b[r], 1)[0] for r in ranks_b]

ax.plot(ranks_b, mean_power_b, 'o-', color=C_B, linewidth=2.5, markersize=9,
        label='Test B Avg Power')
ax.axhline(y=idle_avg, color='gray', linestyle='--', linewidth=1.5,
           label=f'Idle Baseline ({idle_avg:.1f} W)')
for r, p in zip(ranks_b, mean_power_b):
    ax.annotate(f'{p:.1f}W', (r, p), textcoords="offset points",
                xytext=(12, 5), fontsize=9, fontweight='bold', color=C_B)

ax.set_xlabel('MPI Ranks')
ax.set_ylabel('Average Power (W)')
ax.set_title('Plot 4: Average Power Draw vs MPI Ranks')
ax.set_xscale('log', base=2)
ax.set_xticks(ranks_b)
ax.set_xticklabels([str(r) for r in ranks_b])
ax.legend(fontsize=10)
ax.set_ylim(50, max(mean_power_b) * 1.15)
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'plot04_power_vs_ranks.png'))
plt.close()
print("  [4/14] plot04_power_vs_ranks.png")

# ============================================================
# PLOT 5: Time Breakdown by Component — ALL ranks (Test B only, stacked)
# ============================================================
fig, ax = plt.subplots(figsize=(12, 7))

comp_names = ['t_force', 't_neigh', 't_comm (halo)', 't_other (I/O+comm)']
comp_colors = ['#4C72B0', '#55A868', '#C44E52', '#8172B2']
comp_indices = [2, 3, 4, 5]

x_pos = np.arange(len(ranks_b))
bar_width = 0.55
bottoms = np.zeros(len(ranks_b))

for ci, (c_idx, c_name, c_col) in enumerate(zip(comp_indices, comp_names, comp_colors)):
    vals = [stats(test_b[r], c_idx)[0] for r in ranks_b]
    ax.bar(x_pos, vals, bar_width, bottom=bottoms, label=c_name, color=c_col,
           edgecolor='white', linewidth=0.5)
    bottoms += vals

# Add total time label on top
for i, r in enumerate(ranks_b):
    t = stats(test_b[r], 1)[0]
    ax.text(x_pos[i], bottoms[i] + 5, f'{t:.1f}s', ha='center',
            fontweight='bold', fontsize=9)

ax.set_xticks(x_pos)
ax.set_xticklabels([f'N={r}' for r in ranks_b])
ax.set_ylabel('Time (s)')
ax.set_title('Plot 5: Time Breakdown by Component — All MPI Ranks (Test B)')
ax.legend(loc='upper right', fontsize=9)
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'plot05_time_breakdown_all_ranks.png'))
plt.close()
print("  [5/14] plot05_time_breakdown_all_ranks.png")

# ============================================================
# PLOT 6: N=16 Comparison — Energy (A vs B vs C vs C2)
# ============================================================
labels_4 = ['Test A\n(Baseline)', 'Test B\n(Comm ON)', 'Test C\n(Simple Ctrl)', 'Test C2\n(Adaptive)']
colors_4 = [C_A, C_B, C_C, C_C2]

ea = stats(test_a[16], 0); eb = stats(test_b[16], 0)
ec = stats(test_c[16], 0); ec2 = stats(test_c2[16], 0)
energies = [ea[0], eb[0], ec[0], ec2[0]]
energy_err = [ea[1], eb[1], ec[1], ec2[1]]

fig, ax = plt.subplots()
bars = ax.bar(labels_4, energies, color=colors_4, edgecolor='black',
              linewidth=0.5, width=0.6, yerr=energy_err, capsize=5)
annotate_bars(ax, bars, energies, fmt='{:,.0f} J', offset=max(energy_err)+100)

# Percent labels
pct_cb = (ec[0] - eb[0]) / eb[0] * 100
pct_c2b = (ec2[0] - eb[0]) / eb[0] * 100
ax.annotate(f'C vs B: {pct_cb:+.1f}%', xy=(2, ec[0]), xytext=(2.6, ec[0]*1.1),
            fontsize=10, fontweight='bold', color='darkgreen',
            arrowprops=dict(arrowstyle='->', color='darkgreen'))
ax.annotate(f'C2 vs B: {pct_c2b:+.1f}%', xy=(3, ec2[0]), xytext=(2.6, ec2[0]*1.15),
            fontsize=10, fontweight='bold', color=C_C2,
            arrowprops=dict(arrowstyle='->', color=C_C2))

ax.set_ylabel('Total Energy (J)')
ax.set_title('Plot 6: Energy Comparison at N=16')
ax.set_ylim(0, max(energies) * 1.35)
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'plot06_energy_N16.png'))
plt.close()
print("  [6/14] plot06_energy_N16.png")

# ============================================================
# PLOT 7: N=16 Comparison — Time (A vs B vs C vs C2)
# ============================================================
ta = stats(test_a[16], 1); tb = stats(test_b[16], 1)
tc = stats(test_c[16], 1); tc2 = stats(test_c2[16], 1)
times = [ta[0], tb[0], tc[0], tc2[0]]
time_err = [ta[1], tb[1], tc[1], tc2[1]]

fig, ax = plt.subplots()
bars = ax.bar(labels_4, times, color=colors_4, edgecolor='black',
              linewidth=0.5, width=0.6, yerr=time_err, capsize=5)
annotate_bars(ax, bars, times, fmt='{:.1f}s', offset=max(time_err)+1)

pct_t_cb = (tc[0] - tb[0]) / tb[0] * 100
pct_t_c2b = (tc2[0] - tb[0]) / tb[0] * 100
ax.annotate(f'C vs B: {pct_t_cb:+.1f}%', xy=(2, tc[0]), xytext=(2.5, tc[0]*1.05),
            fontsize=10, fontweight='bold', color='darkgreen',
            arrowprops=dict(arrowstyle='->', color='darkgreen'))
ax.annotate(f'C2 vs B: {pct_t_c2b:+.1f}%', xy=(3, tc2[0]), xytext=(2.6, tc2[0]*1.05),
            fontsize=10, fontweight='bold', color=C_C2,
            arrowprops=dict(arrowstyle='->', color=C_C2))

ax.set_ylabel('Execution Time (s)')
ax.set_title('Plot 7: Execution Time Comparison at N=16')
ax.set_ylim(0, max(times) * 1.25)
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'plot07_time_N16.png'))
plt.close()
print("  [7/14] plot07_time_N16.png")

# ============================================================
# PLOT 8: N=16 Performance Comparison
# ============================================================
pa = stats(test_a[16], 6); pb = stats(test_b[16], 6)
pc = stats(test_c[16], 6); pc2 = stats(test_c2[16], 6)
perfs = [pa[0]/1e6, pb[0]/1e6, pc[0]/1e6, pc2[0]/1e6]
perf_err = [pa[1]/1e6, pb[1]/1e6, pc[1]/1e6, pc2[1]/1e6]

fig, ax = plt.subplots()
bars = ax.bar(labels_4, perfs, color=colors_4, edgecolor='black',
              linewidth=0.5, width=0.6, yerr=perf_err, capsize=5)
annotate_bars(ax, bars, perfs, fmt='{:.2f}M', offset=max(perf_err)+0.05)
ax.set_ylabel('Performance (M atom-steps/s)')
ax.set_title('Plot 8: Performance Comparison at N=16')
ax.set_ylim(0, max(perfs) * 1.2)
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'plot08_perf_N16.png'))
plt.close()
print("  [8/14] plot08_perf_N16.png")

# ============================================================
# PLOT 9: N=16 Component Breakdown (4 panels)
# ============================================================
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
component_info = [
    (2, 'Force Computation (CPU-bound)', axes[0,0]),
    (3, 'Neighbor List Build (CPU-bound)', axes[0,1]),
    (4, 'MPI Halo Exchange (sync-sensitive)', axes[1,0]),
    (5, 'Other (I/O, setup, comm phase)', axes[1,1]),
]

for idx, title, ax in component_info:
    vals = [stats(test_a[16], idx)[0], stats(test_b[16], idx)[0],
            stats(test_c[16], idx)[0], stats(test_c2[16], idx)[0]]
    errs = [stats(test_a[16], idx)[1], stats(test_b[16], idx)[1],
            stats(test_c[16], idx)[1], stats(test_c2[16], idx)[1]]
    bars = ax.bar(labels_4, vals, color=colors_4, edgecolor='black',
                  linewidth=0.5, width=0.55, yerr=errs, capsize=4)
    annotate_bars(ax, bars, vals, fmt='{:.2f}s', offset=max(errs)+0.1, fontsize=9)
    ax.set_ylabel('Time (s)')
    ax.set_title(title, fontsize=11)
    ax.set_ylim(0, max(vals) * 1.3)

fig.suptitle('Plot 9: Per-Component Time at N=16', fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'plot09_component_N16.png'))
plt.close()
print("  [9/14] plot09_component_N16.png")

# ============================================================
# PLOT 10: Overhead — C and C2 vs B (Energy + Time side-by-side)
# ============================================================
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))

oh_ce = pct_cb
oh_c2e = pct_c2b
bars1 = ax1.bar(['Test C\n(Simple)', 'Test C2\n(Adaptive)'], [oh_ce, oh_c2e],
                color=[C_C, C_C2], edgecolor='black', linewidth=0.5, width=0.5)
for bar, val in zip(bars1, [oh_ce, oh_c2e]):
    y = bar.get_height() + (2 if val >= 0 else -3)
    ax1.text(bar.get_x() + bar.get_width()/2, y,
             f'{val:+.1f}%', ha='center', fontweight='bold', fontsize=13)
ax1.set_ylabel('Energy Change vs Test B (%)')
ax1.set_title('Energy Overhead vs Test B (N=16)')
ax1.axhline(y=0, color='black', linewidth=0.8)

oh_ct = pct_t_cb
oh_c2t = pct_t_c2b
bars2 = ax2.bar(['Test C\n(Simple)', 'Test C2\n(Adaptive)'], [oh_ct, oh_c2t],
                color=[C_C, C_C2], edgecolor='black', linewidth=0.5, width=0.5)
for bar, val in zip(bars2, [oh_ct, oh_c2t]):
    y = bar.get_height() + (2 if val >= 0 else -3)
    ax2.text(bar.get_x() + bar.get_width()/2, y,
             f'{val:+.1f}%', ha='center', fontweight='bold', fontsize=13)
ax2.set_ylabel('Time Change vs Test B (%)')
ax2.set_title('Time Overhead vs Test B (N=16)')
ax2.axhline(y=0, color='black', linewidth=0.8)

plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'plot10_overhead.png'))
plt.close()
print("  [10/14] plot10_overhead.png")

# ============================================================
# PLOT 11: Phase Timeline — C vs C2
# ============================================================
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

# Test C
phases = ['COMPUTE (2.0 GHz)', 'I/O (1.2 GHz)', 'COMM (2.0 GHz)', 'COMPUTE (2.0 GHz)']
t_c_total = stats(test_c[16], 1)[0]
compute_half = (t_c_total - ctrl_c_log['io_duration'] - ctrl_c_log['comm_duration']) / 2
dur_c = [compute_half, ctrl_c_log['io_duration'], ctrl_c_log['comm_duration'], compute_half]
bar_colors_c = ['#55A868', '#8172B2', '#C44E52', '#55A868']
ax1.barh(phases, dur_c, color=bar_colors_c, edgecolor='black', linewidth=0.5, height=0.6)
for i, d in enumerate(dur_c):
    if d > 1:
        ax1.text(d/2, i, f'{d:.1f}s', ha='center', va='center', fontsize=10,
                 fontweight='bold', color='white')
    else:
        ax1.text(d+0.3, i, f'{d:.3f}s', ha='left', va='center', fontsize=9)
ax1.set_title(f'comm_freq_controller (Test C) --- t_total: {t_c_total:.1f}s  (+{pct_t_cb:.1f}% vs B)',
              fontweight='bold')
ax1.set_xlabel('Duration (s)')

# Test C2
t_c2_total = stats(test_c2[16], 1)[0]
compute_half_c2 = (t_c2_total - ctrl_c2_log['io_duration'] - ctrl_c2_log['comm_duration']) / 2
dur_c2 = [compute_half_c2, ctrl_c2_log['io_duration'], ctrl_c2_log['comm_duration'], compute_half_c2]
ax2.barh(phases, dur_c2, color=bar_colors_c, edgecolor='black', linewidth=0.5, height=0.6)
for i, d in enumerate(dur_c2):
    if d > 1:
        ax2.text(d/2, i, f'{d:.1f}s', ha='center', va='center', fontsize=10,
                 fontweight='bold', color='white')
    else:
        ax2.text(d+0.3, i, f'{d:.3f}s', ha='left', va='center', fontsize=9)
ax2.set_title(f'integrated_freq_controller (Test C2) --- t_total: {t_c2_total:.1f}s  (+{pct_t_c2b:.0f}% vs B)',
              fontweight='bold')
ax2.set_xlabel('Duration (s)')

plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'plot11_phase_timeline.png'))
plt.close()
print("  [11/14] plot11_phase_timeline.png")

# ============================================================
# PLOT 12: Idle Power Distribution
# ============================================================
fig, ax = plt.subplots(figsize=(9, 5))
ax.hist(idle_power_W, bins=12, color=C_A, edgecolor='black', linewidth=0.5, alpha=0.8)
ax.axvline(x=idle_avg, color='red', linewidth=2, linestyle='--',
           label=f'Mean: {idle_avg:.2f} W')
ax.axvspan(idle_avg - idle_std, idle_avg + idle_std, alpha=0.15, color='red',
           label=f'$\\pm$1$\\sigma$: {idle_std:.3f} W')
ax.set_xlabel('Idle Power (W)')
ax.set_ylabel('Count')
ax.set_title(f'Plot 12: Idle Power Distribution (25 trials, mean={idle_avg:.2f}W)')
ax.legend()
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'plot12_idle_power.png'))
plt.close()
print("  [12/14] plot12_idle_power.png")

# ============================================================
# PLOT 13: Energy Variability Box Plots — Test B, all ranks
# ============================================================
fig, ax = plt.subplots(figsize=(11, 6))
energy_data = [[d[0] for d in test_b[r]] for r in ranks_b]
bp = ax.boxplot(energy_data, positions=range(len(ranks_b)), widths=0.5,
                patch_artist=True, tick_labels=[f'N={r}\n({len(test_b[r])} trials)' for r in ranks_b])
for patch in bp['boxes']:
    patch.set_facecolor(C_B)
    patch.set_alpha(0.6)
# Add means
means = [np.mean(d) for d in energy_data]
ax.plot(range(len(ranks_b)), means, 'D', color='red', markersize=7, zorder=5, label='Mean')
for i, m in enumerate(means):
    ax.annotate(f'{m:,.0f}J', (i, m), textcoords="offset points",
                xytext=(10, -10), fontsize=8.5, color='red', fontweight='bold')

ax.set_ylabel('Total Energy (J)')
ax.set_title('Plot 13: Energy Variability — Test B (all MPI ranks)')
ax.legend()
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'plot13_energy_variability.png'))
plt.close()
print("  [13/14] plot13_energy_variability.png")

# ============================================================
# PLOT 14: Strong Scaling Efficiency (Test B)
# ============================================================
fig, ax = plt.subplots(figsize=(10, 6))
perf_1 = stats(test_b[1], 6)[0]
efficiencies = []
for r in ranks_b:
    p = stats(test_b[r], 6)[0]
    eff = (p / (perf_1 * r)) * 100
    efficiencies.append(eff)

ax.plot(ranks_b, efficiencies, 'o-', color=C_B, linewidth=2.5, markersize=9,
        label='Parallel Efficiency')
ax.axhline(y=100, color='gray', linestyle='--', linewidth=1.5, label='Ideal (100%)')
for r, e in zip(ranks_b, efficiencies):
    ax.annotate(f'{e:.1f}%', (r, e), textcoords="offset points",
                xytext=(10, 8), fontsize=10, fontweight='bold', color=C_B)

ax.set_xlabel('MPI Ranks')
ax.set_ylabel('Parallel Efficiency (%)')
ax.set_title('Plot 14: Strong Scaling Efficiency (Test B)')
ax.set_xscale('log', base=2)
ax.set_xticks(ranks_b)
ax.set_xticklabels([str(r) for r in ranks_b])
ax.set_ylim(0, 110)
ax.legend(fontsize=10)
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'plot14_scaling_efficiency.png'))
plt.close()
print("  [14/14] plot14_scaling_efficiency.png")


# ============================================================
# SUMMARY TABLE
# ============================================================
print("\n" + "=" * 95)
print("  RESULTS SUMMARY — All MPI Ranks")
print("=" * 95)

print("\n  --- Test B Scaling ---")
print(f"  {'Ranks':<8} {'Trials':<8} {'Energy (J)':<16} {'Time (s)':<14} {'Perf (M as/s)':<16} {'Avg Power (W)'}")
print("  " + "-" * 80)
for r in ranks_b:
    n = len(test_b[r])
    me, se = stats(test_b[r], 0)
    mt, st = stats(test_b[r], 1)
    mp = stats(test_b[r], 6)[0] / 1e6
    pw = me / mt
    print(f"  N={r:<4} {n:<8} {me:>10,.0f} +/- {se:>6,.0f}   {mt:>7.1f} +/- {st:.1f}   {mp:>8.2f}         {pw:.1f}")

print(f"\n  --- N=16 Comparison ---")
print(f"  {'Test':<10} {'Energy (J)':<14} {'Time (s)':<12} {'t_force':<10} {'t_neigh':<10} {'t_comm':<10} {'t_other':<10} {'Perf (M)'}")
print("  " + "-" * 90)
for name, data in [('A', test_a[16]), ('B', test_b[16]), ('C', test_c[16]), ('C2', test_c2[16])]:
    e = stats(data, 0)[0]
    t = stats(data, 1)[0]
    tf = stats(data, 2)[0]
    tn = stats(data, 3)[0]
    tc_val = stats(data, 4)[0]
    to = stats(data, 5)[0]
    p = stats(data, 6)[0] / 1e6
    print(f"  {name:<10} {e:>10,.0f}     {t:>7.1f}     {tf:>7.2f}    {tn:>7.2f}    {tc_val:>7.3f}    {to:>7.2f}    {p:>7.2f}")

print(f"\n  --- Controller Results at N=16 ---")
print(f"  Test C  (comm_freq_ctrl):       Energy={ec[0]:,.0f}J, Time={tc[0]:.1f}s, vs B: {pct_cb:+.1f}% energy, {pct_t_cb:+.1f}% time")
print(f"  Test C2 (integrated_freq_ctrl): Energy={ec2[0]:,.0f}J, Time={tc2[0]:.1f}s, vs B: {pct_c2b:+.1f}% energy, {pct_t_c2b:+.1f}% time")
print(f"  Idle Power: {idle_avg:.2f} +/- {idle_std:.3f} W (25 trials)")

print(f"\nAll 14 plots saved to: {out_dir}")
