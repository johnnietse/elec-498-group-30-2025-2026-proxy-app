#!/usr/bin/env python3
"""
Complete Analysis of Manual Test Results — Feb 28, 2026
Data from: test_results_from_running_manual_commands_guide.txt

Tests:
  A  = Baseline (performance governor, comm phase OFF)
  B  = Comm phase ON, no controller (performance governor)
  C  = Comm phase ON + comm_freq_controller.py
  C2 = Comm phase ON + integrated_freq_controller.py

MPI ranks tested: 1, 2, 4, 8, 16, 30  (A and B)
                  16 only              (C and C2)

NOTE: Some Test A energy values at N=1 have RAPL counter wraparound issues
      (e.g. 2420 J for a 500s run is clearly wrong). These are filtered out.
"""
import os
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.rcParams.update({
    'figure.figsize': (10, 6), 'figure.facecolor': 'white',
    'axes.facecolor': '#f8f9fa', 'axes.edgecolor': '#dee2e6',
    'axes.grid': True, 'grid.alpha': 0.3,
    'font.size': 11, 'axes.titlesize': 14, 'axes.labelsize': 12,
    'savefig.bbox': 'tight', 'savefig.dpi': 150,
})

out_dir = os.path.dirname(os.path.abspath(__file__))

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
# TEST A — Baseline (comm phase OFF, performance governor)
# ============================================================
# Columns: energy_j, t_total, t_force, t_neigh, t_comm, t_other, perf
# NOTE: Test A N=1 only ran 6 trials, trial 6 had RAPL wraparound (2420 J)
#       Test A N=16 only ran 1 trial
test_a = {
    1: [
        # trial 1-5 valid, trial 6 energy=2420 is RAPL wraparound → exclude
        (39609.811, 498.682, 390.263, 63.928, 2.763, 41.727, 1682157),
        (45907.620, 498.749, 390.408, 63.885, 2.720, 41.735, 1681931),
        (41897.955, 498.697, 390.259, 63.896, 2.759, 41.782, 1682104),
        (42780.254, 498.674, 390.291, 63.889, 2.732, 41.762, 1682181),
        (40575.270, 498.403, 390.165, 63.832, 2.691, 41.716, 1683096),
        # trial 6: 2420.265 J — RAPL counter wrapped, energy invalid, exclude
    ],
    16: [
        (7299.031, 67.887, 29.394, 4.756, 0.797, 32.940, 12356683),
    ],
}

# ============================================================
# TEST B — Comm phase ON, no controller (performance governor)
# ============================================================
# From results_manual_test_b.csv (final clean version)
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
        (9983.275, 91.570, 49.318, 7.972, 1.074, 33.207, 9160857),
        (8956.522, 90.263, 49.179, 7.969, 1.079, 32.036, 9293509),
        (11886.480, 90.190, 49.111, 7.965, 1.105, 32.009, 9301018),
        (9588.311, 91.153, 49.140, 8.038, 1.056, 32.919, 9202748),
    ],
    16: [
        (9032.496, 68.176, 29.400, 4.755, 0.862, 33.160, 12304255),
        (9813.485, 67.925, 29.401, 4.749, 0.798, 32.977, 12349778),
        (7412.733, 68.005, 29.386, 4.738, 0.840, 33.042, 12335282),
        (7418.736, 67.184, 29.380, 4.738, 0.812, 32.255, 12485959),
        (10392.754, 67.894, 29.367, 4.740, 0.806, 32.981, 12355525),
        (6914.451, 67.201, 29.375, 4.733, 0.800, 32.293, 12482894),
        (6795.201, 67.864, 29.370, 4.745, 0.796, 32.953, 12360943),
        (6755.405, 67.865, 29.359, 4.740, 0.829, 32.937, 12360798),
        (8640.529, 67.914, 29.369, 4.739, 0.834, 32.973, 12351748),
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

# ============================================================
# TEST C — comm_freq_controller.py (N=16 only)
# ============================================================
test_c = {
    16: [
        (11093.842, 68.218, 29.405, 4.761, 0.844, 33.208, 12296807),
    ],
}

# ============================================================
# TEST C2 — integrated_freq_controller.py (N=16 only)
# ============================================================
test_c2 = {
    16: [
        (12933.609, 106.763, 45.000, 7.889, 20.511, 33.363, 7857247),
    ],
}

# I/O and Comm phase durations (from logs)
io_dur_approx = 31.5   # ~31.4-31.5 seconds across all 16-rank runs
comm_dur_c = 0.049      # Test C comm phase
comm_dur_c2 = 0.039     # Test C2 comm phase
comm_dur_b = 0.027       # Test B comm phase

# ============================================================
# HELPER FUNCTIONS
# ============================================================
def stats(data_list, idx):
    """Return mean, std for a given column index."""
    vals = [d[idx] for d in data_list]
    return np.mean(vals), np.std(vals)

def annotate_bars(ax, bars, values, fmt='{:.0f}', offset=0, fontsize=10):
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + offset,
                fmt.format(val), ha='center', va='bottom', fontweight='bold', fontsize=fontsize)

# ============================================================
# GRAPH 1: Total Energy Comparison (N=16, A vs B vs C vs C2)
# ============================================================
labels_4test = ['Test A\n(Baseline)', 'Test B\n(Comm ON)', 'Test C\n(Simple Ctrl)', 'Test C2\n(Adaptive Ctrl)']
colors_4test = ['#4C72B0', '#DD8452', '#55A868', '#C44E52']

e_a = stats(test_a[16], 0)
e_b = stats(test_b[16], 0)
e_c = stats(test_c[16], 0)
e_c2 = stats(test_c2[16], 0)
energies_16 = [e_a[0], e_b[0], e_c[0], e_c2[0]]
energy_errs = [e_a[1], e_b[1], e_c[1], e_c2[1]]

fig, ax = plt.subplots()
bars = ax.bar(labels_4test, energies_16, color=colors_4test, edgecolor='black',
              linewidth=0.5, width=0.6, yerr=energy_errs, capsize=5)
annotate_bars(ax, bars, energies_16, fmt='{:.0f} J', offset=max(energy_errs)+50)
ax.set_ylabel('Total Energy (J)')
ax.set_title('Graph 1: Total Energy Comparison (N=16)')
ax.set_ylim(0, max(energies_16) * 1.25)
# Savings annotations
pct_cb = (e_c[0] - e_b[0]) / e_b[0] * 100
ax.annotate(f'C vs B: {pct_cb:+.1f}%', xy=(2, e_c[0]), xytext=(2.5, e_c[0]*1.15),
            fontsize=10, fontweight='bold', color='green',
            arrowprops=dict(arrowstyle='->', color='green'))
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'graph1_energy_comparison.png'))
plt.close()
print(f"  Graph 1 saved. C vs B: {pct_cb:+.1f}% energy")

# ============================================================
# GRAPH 2: Total Time Comparison (N=16)
# ============================================================
t_a = stats(test_a[16], 1)
t_b = stats(test_b[16], 1)
t_c = stats(test_c[16], 1)
t_c2 = stats(test_c2[16], 1)
times_16 = [t_a[0], t_b[0], t_c[0], t_c2[0]]
time_errs = [t_a[1], t_b[1], t_c[1], t_c2[1]]

fig, ax = plt.subplots()
bars = ax.bar(labels_4test, times_16, color=colors_4test, edgecolor='black',
              linewidth=0.5, width=0.6, yerr=time_errs, capsize=5)
annotate_bars(ax, bars, times_16, fmt='{:.1f}s', offset=max(time_errs)+0.5)
ax.set_ylabel('Execution Time (s)')
ax.set_title('Graph 2: Execution Time Comparison (N=16)')
ax.set_ylim(0, max(times_16) * 1.2)
pct_time_cb = (t_c[0] - t_b[0]) / t_b[0] * 100
pct_time_c2b = (t_c2[0] - t_b[0]) / t_b[0] * 100
ax.annotate(f'C vs B: {pct_time_cb:+.1f}%', xy=(2, t_c[0]), xytext=(2.5, t_c[0]*1.08),
            fontsize=10, fontweight='bold', color='green',
            arrowprops=dict(arrowstyle='->', color='green'))
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'graph2_time_comparison.png'))
plt.close()
print(f"  Graph 2 saved. C vs B time: {pct_time_cb:+.1f}%, C2 vs B: {pct_time_c2b:+.1f}%")

# ============================================================
# GRAPH 4: Average Power (N=16)
# ============================================================
# Wall = t_total + io_dur + comm_dur (these are embedded in t_total already for B/C/C2
# Actually, t_total includes I/O + comm time. So avg power = energy / t_total
# But wait — the I/O duration is ~31.5s and is INCLUDED in t_other.
# t_total already includes everything.
walls_16 = times_16  # t_total already includes I/O + comm
powers_16 = [e/t for e, t in zip(energies_16, walls_16)]

fig, ax = plt.subplots()
bars = ax.bar(labels_4test, powers_16, color=colors_4test, edgecolor='black',
              linewidth=0.5, width=0.6)
annotate_bars(ax, bars, powers_16, fmt='{:.1f} W', offset=1)
ax.axhline(y=idle_avg, color='gray', linestyle='--', linewidth=1.5,
           label=f'Idle ({idle_avg:.1f} W)')
ax.set_ylabel('Average Power (W)')
ax.set_title('Graph 4: Average Power (N=16)')
ax.set_ylim(0, max(powers_16) * 1.25)
ax.legend()
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'graph4_avg_power.png'))
plt.close()
print(f"  Graph 4 saved.")

# ============================================================
# GRAPH 10: Performance (atom-steps/s) (N=16)
# ============================================================
p_a = stats(test_a[16], 6)
p_b = stats(test_b[16], 6)
p_c = stats(test_c[16], 6)
p_c2 = stats(test_c2[16], 6)
perfs_16 = [p_a[0]/1e6, p_b[0]/1e6, p_c[0]/1e6, p_c2[0]/1e6]
perf_errs = [p_a[1]/1e6, p_b[1]/1e6, p_c[1]/1e6, p_c2[1]/1e6]

fig, ax = plt.subplots()
bars = ax.bar(labels_4test, perfs_16, color=colors_4test, edgecolor='black',
              linewidth=0.5, width=0.6, yerr=perf_errs, capsize=5)
annotate_bars(ax, bars, perfs_16, fmt='{:.2f}M', offset=max(perf_errs)+0.05)
ax.set_ylabel('Performance (M atom-steps/s)')
ax.set_title('Graph 10: Performance Comparison (N=16)')
ax.set_ylim(0, max(perfs_16) * 1.2)
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'graph10_performance.png'))
plt.close()
print(f"  Graph 10 saved.")

# ============================================================
# GRAPH 11: Energy Efficiency (perf per watt) (N=16)
# ============================================================
eff_16 = [p / w for p, w in zip([p_a[0], p_b[0], p_c[0], p_c2[0]], powers_16)]

fig, ax = plt.subplots()
bars = ax.bar(labels_4test, [e/1e6 for e in eff_16], color=colors_4test,
              edgecolor='black', linewidth=0.5, width=0.6)
annotate_bars(ax, bars, [e/1e6 for e in eff_16], fmt='{:.3f}', offset=0.002)
ax.set_ylabel('Efficiency (M atom-steps/s per W)')
ax.set_title('Graph 11: Energy Efficiency (Perf / Avg Power)')
ax.set_ylim(0, max([e/1e6 for e in eff_16]) * 1.15)
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'graph11_energy_efficiency.png'))
plt.close()
print(f"  Graph 11 saved.")

# ============================================================
# GRAPH 14: Time Breakdown by Component (N=16)
# ============================================================
fig, ax = plt.subplots(figsize=(10, 7))
x = np.arange(4)
w = 0.55
comps = [2, 3, 4, 5]  # t_force, t_neigh, t_comm, t_other indices
comp_names = ['t_force', 't_neigh', 't_comm (halo)', 't_other (I/O+comm)']
comp_colors_list = ['#4C72B0', '#55A868', '#C44E52', '#8172B2']

# Get mean values for each test at N=16
test_data_16 = [
    [stats(test_a[16], i)[0] for i in comps],
    [stats(test_b[16], i)[0] for i in comps],
    [stats(test_c[16], i)[0] for i in comps],
    [stats(test_c2[16], i)[0] for i in comps],
]

bottoms = np.zeros(4)
for ci, (comp_col, comp_label) in enumerate(zip(comp_colors_list, comp_names)):
    vals = [td[ci] for td in test_data_16]
    ax.bar(x, vals, w, bottom=bottoms, label=comp_label, color=comp_col)
    bottoms += vals

ax.set_xticks(x)
ax.set_xticklabels(labels_4test)
ax.set_ylabel('Time (s)')
ax.set_title('Graph 14: Time Breakdown by Component (N=16)')
ax.legend(loc='upper left')
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'graph14_time_breakdown.png'))
plt.close()
print(f"  Graph 14 saved.")

# ============================================================
# GRAPH: Component Breakdown (individual subplots)
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
    bars = ax.bar(labels_4test, vals, color=colors_4test, edgecolor='black',
                  linewidth=0.5, width=0.55, yerr=errs, capsize=4)
    annotate_bars(ax, bars, vals, fmt='{:.2f}s', offset=max(errs)+0.1, fontsize=9)
    ax.set_ylabel('Time (s)')
    ax.set_title(title)
    ax.set_ylim(0, max(vals) * 1.25)

fig.suptitle('Per-Component Time Breakdown (N=16)', fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'graph_component_breakdown.png'))
plt.close()
print(f"  Component breakdown saved.")

# ============================================================
# GRAPH 15: Dynamic vs Idle Energy (N=16)
# ============================================================
fig, ax = plt.subplots(figsize=(10, 6))
idle_energies = [idle_avg * t for t in walls_16]
dynamic_energies = [e - ie for e, ie in zip(energies_16, idle_energies)]

x15 = np.arange(4)
w15 = 0.5
bars_idle = ax.bar(x15, idle_energies, w15, label=f'Idle ({idle_avg:.1f}W × time)',
                   color='#95a5a6', edgecolor='black', linewidth=0.5)
bars_dyn = ax.bar(x15, dynamic_energies, w15, bottom=idle_energies,
                  label='Dynamic (compute overhead)', color=colors_4test,
                  edgecolor='black', linewidth=0.5)
for i in range(4):
    ax.text(x15[i], energies_16[i] + 100, f'{energies_16[i]:.0f} J',
            ha='center', fontweight='bold', fontsize=10)
ax.set_xticks(x15)
ax.set_xticklabels(labels_4test)
ax.set_ylabel('Energy (J)')
ax.set_title('Graph 15: Dynamic vs Idle Energy (N=16)')
ax.legend()
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'graph15_dynamic_vs_idle.png'))
plt.close()
print(f"  Graph 15 saved.")

# ============================================================
# GRAPH 16: Phase Timeline (C vs C2)
# ============================================================
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

# comm_freq_controller
phases = ['COMPUTE (2.0GHz)', 'I/O (1.2GHz)', 'COMM', 'COMPUTE (2.0GHz)']
dur_c_phases = [68.218/2, 31.41, 0.049, 68.218/2]
ax1.barh(phases, dur_c_phases, color=['#55A868','#8172B2','#C44E52','#55A868'],
         edgecolor='black', linewidth=0.5, height=0.6)
for i, d in enumerate(dur_c_phases):
    if d > 1:
        ax1.text(d/2, i, f'{d:.1f}s', ha='center', va='center', fontsize=10,
                 fontweight='bold', color='white')
    else:
        ax1.text(d+0.3, i, f'{d:.3f}s', ha='left', va='center', fontsize=9)
ax1.set_title('comm_freq_controller — t_total: 68.2s ✅ (≈ Test B)', fontweight='bold')
ax1.set_xlabel('Duration (s)')

# integrated_freq_controller  
dur_c2_phases = [106.763/2, 31.51, 0.039, 106.763/2]
ax2.barh(phases, dur_c2_phases, color=['#55A868','#8172B2','#C44E52','#55A868'],
         edgecolor='black', linewidth=0.5, height=0.6)
for i, d in enumerate(dur_c2_phases):
    if d > 1:
        ax2.text(d/2, i, f'{d:.1f}s', ha='center', va='center', fontsize=10,
                 fontweight='bold', color='white')
    else:
        ax2.text(d+0.3, i, f'{d:.3f}s', ha='left', va='center', fontsize=9)
ax2.set_title(f'integrated_freq_controller — t_total: 106.8s ❌ (+{pct_time_c2b:.0f}%)', fontweight='bold')
ax2.set_xlabel('Duration (s)')
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'graph16_phase_timeline.png'))
plt.close()
print(f"  Graph 16 saved.")

# ============================================================
# GRAPH 8/9: Overhead (energy + time)
# ============================================================
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))

# Energy overhead vs B
oh_cb_e = (e_c[0] - e_b[0]) / e_b[0] * 100
oh_c2b_e = (e_c2[0] - e_b[0]) / e_b[0] * 100
bars1 = ax1.bar(['Test C\n(Simple)', 'Test C2\n(Adaptive)'], [oh_cb_e, oh_c2b_e],
                color=['#55A868', '#C44E52'], edgecolor='black', linewidth=0.5, width=0.5)
for bar, val in zip(bars1, [oh_cb_e, oh_c2b_e]):
    y_pos = bar.get_height() + (1 if val >= 0 else -3)
    ax1.text(bar.get_x() + bar.get_width()/2, y_pos,
             f'{val:+.1f}%', ha='center', fontweight='bold', fontsize=12)
ax1.set_ylabel('Energy Change vs Test B (%)')
ax1.set_title('Graph 8: Energy Overhead vs Test B')
ax1.axhline(y=0, color='black', linewidth=0.8)

# Time overhead vs B
oh_cb_t = (t_c[0] - t_b[0]) / t_b[0] * 100
oh_c2b_t = (t_c2[0] - t_b[0]) / t_b[0] * 100
bars2 = ax2.bar(['Test C\n(Simple)', 'Test C2\n(Adaptive)'], [oh_cb_t, oh_c2b_t],
                color=['#55A868', '#C44E52'], edgecolor='black', linewidth=0.5, width=0.5)
for bar, val in zip(bars2, [oh_cb_t, oh_c2b_t]):
    y_pos = bar.get_height() + (1 if val >= 0 else -3)
    ax2.text(bar.get_x() + bar.get_width()/2, y_pos,
             f'{val:+.1f}%', ha='center', fontweight='bold', fontsize=12)
ax2.set_ylabel('Time Change vs Test B (%)')
ax2.set_title('Graph 9: Time Overhead vs Test B')
ax2.axhline(y=0, color='black', linewidth=0.8)
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'graph8_9_overhead.png'))
plt.close()
print(f"  Graph 8/9 saved.")

# ============================================================
# GRAPH: Scaling — Energy vs MPI Ranks (Test B only; has multi-rank data)
# ============================================================
ranks_b = sorted(test_b.keys())
mean_energy_b = [stats(test_b[r], 0)[0] for r in ranks_b]
std_energy_b = [stats(test_b[r], 0)[1] for r in ranks_b]
mean_time_b = [stats(test_b[r], 1)[0] for r in ranks_b]
std_time_b = [stats(test_b[r], 1)[1] for r in ranks_b]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

# Energy scaling
ax1.errorbar(ranks_b, mean_energy_b, yerr=std_energy_b, fmt='o-', color='#DD8452',
             capsize=5, linewidth=2, markersize=8, label='Test B Energy')
for r, e in zip(ranks_b, mean_energy_b):
    ax1.annotate(f'{e:.0f}J', (r, e), textcoords="offset points", xytext=(10, 10),
                 fontsize=9, fontweight='bold')
ax1.set_xlabel('MPI Ranks')
ax1.set_ylabel('Total Energy (J)')
ax1.set_title('Energy Scaling vs MPI Ranks (Test B)')
ax1.set_xscale('log', base=2)
ax1.set_xticks(ranks_b)
ax1.set_xticklabels([str(r) for r in ranks_b])
ax1.legend()

# Time scaling
ax2.errorbar(ranks_b, mean_time_b, yerr=std_time_b, fmt='s-', color='#4C72B0',
             capsize=5, linewidth=2, markersize=8, label='Test B Time')
for r, t in zip(ranks_b, mean_time_b):
    ax2.annotate(f'{t:.1f}s', (r, t), textcoords="offset points", xytext=(10, 10),
                 fontsize=9, fontweight='bold')
ax2.set_xlabel('MPI Ranks')
ax2.set_ylabel('Execution Time (s)')
ax2.set_title('Time Scaling vs MPI Ranks (Test B)')
ax2.set_xscale('log', base=2)
ax2.set_xticks(ranks_b)
ax2.set_xticklabels([str(r) for r in ranks_b])
ax2.legend()

plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'graph_scaling_ranks.png'))
plt.close()
print(f"  Scaling graph saved.")

# ============================================================
# GRAPH: Performance Scaling (Test B across ranks)
# ============================================================
mean_perf_b = [stats(test_b[r], 6)[0]/1e6 for r in ranks_b]
ideal_perf = [mean_perf_b[0] * r for r in ranks_b]

fig, ax = plt.subplots()
ax.plot(ranks_b, mean_perf_b, 'o-', color='#DD8452', linewidth=2, markersize=8,
        label='Actual Performance')
ax.plot(ranks_b, ideal_perf, '--', color='gray', linewidth=1.5, label='Ideal (linear) Scaling')
for r, p in zip(ranks_b, mean_perf_b):
    ax.annotate(f'{p:.1f}M', (r, p), textcoords="offset points", xytext=(10, 5),
                fontsize=9, fontweight='bold')
ax.set_xlabel('MPI Ranks')
ax.set_ylabel('Performance (M atom-steps/s)')
ax.set_title('Performance Scaling vs MPI Ranks (Test B)')
ax.set_xscale('log', base=2)
ax.set_xticks(ranks_b)
ax.set_xticklabels([str(r) for r in ranks_b])
ax.legend()
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'graph_perf_scaling.png'))
plt.close()
print(f"  Performance scaling graph saved.")

# ============================================================
# GRAPH: Idle Power Histogram
# ============================================================
fig, ax = plt.subplots(figsize=(8, 5))
ax.hist(idle_power_W, bins=15, color='#4C72B0', edgecolor='black', linewidth=0.5, alpha=0.8)
ax.axvline(x=idle_avg, color='red', linewidth=2, linestyle='--',
           label=f'Mean: {idle_avg:.2f} W')
ax.axvspan(idle_avg - idle_std, idle_avg + idle_std, alpha=0.15, color='red',
           label=f'±1σ: {idle_std:.3f} W')
ax.set_xlabel('Idle Power (W)')
ax.set_ylabel('Count')
ax.set_title(f'Idle Power Distribution (25 trials, mean={idle_avg:.2f}W, σ={idle_std:.3f}W)')
ax.legend()
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'graph_idle_power.png'))
plt.close()
print(f"  Idle power histogram saved.")

# ============================================================
# GRAPH: Energy Variability Box Plot (Test B, all ranks)
# ============================================================
fig, ax = plt.subplots(figsize=(10, 6))
energy_data_b = [sorted([d[0] for d in test_b[r]]) for r in ranks_b]
bp = ax.boxplot(energy_data_b, positions=range(len(ranks_b)), widths=0.5,
                patch_artist=True, labels=[str(r) for r in ranks_b])
for patch in bp['boxes']:
    patch.set_facecolor('#DD8452')
    patch.set_alpha(0.7)
ax.set_xlabel('MPI Ranks')
ax.set_ylabel('Total Energy (J)')
ax.set_title('Energy Variability Across Trials (Test B)')
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'graph_energy_variability.png'))
plt.close()
print(f"  Energy variability box plot saved.")

# ============================================================
# SUMMARY TABLE
# ============================================================
print("\n" + "=" * 90)
print("  RESULTS SUMMARY — N=16 MPI Ranks")
print("=" * 90)
print(f"  {'Metric':<20} {'Test A':<15} {'Test B':<15} {'Test C':<15} {'Test C2':<15} {'C vs B':<10} {'C2 vs B'}")
print("-" * 90)

metrics = [
    ('Energy (J)', 0, '{:.0f}'),
    ('Time (s)', 1, '{:.1f}'),
    ('t_force (s)', 2, '{:.2f}'),
    ('t_neigh (s)', 3, '{:.2f}'),
    ('t_comm (s)', 4, '{:.3f}'),
    ('t_other (s)', 5, '{:.2f}'),
]

for name, idx, fmt in metrics:
    va = stats(test_a[16], idx)[0]
    vb = stats(test_b[16], idx)[0]
    vc = stats(test_c[16], idx)[0]
    vc2 = stats(test_c2[16], idx)[0]
    cb = f"{(vc-vb)/vb*100:+.1f}%"
    c2b = f"{(vc2-vb)/vb*100:+.1f}%"
    print(f"  {name:<20} {fmt.format(va):<15} {fmt.format(vb):<15} {fmt.format(vc):<15} {fmt.format(vc2):<15} {cb:<10} {c2b}")

print(f"  {'Performance':<20} {stats(test_a[16],6)[0]:,.0f}{'':>4} {stats(test_b[16],6)[0]:,.0f}{'':>4} {stats(test_c[16],6)[0]:,.0f}{'':>4} {stats(test_c2[16],6)[0]:,.0f}")
print(f"  {'Avg Power (W)':<20} {powers_16[0]:.1f}{'':>12} {powers_16[1]:.1f}{'':>12} {powers_16[2]:.1f}{'':>12} {powers_16[3]:.1f}")
print(f"  {'Idle Power (W)':<20} {idle_avg:.2f} ± {idle_std:.3f} (25 trials)")

print(f"\n  ✅ Test C  (comm ctrl):     {pct_cb:+.1f}% energy vs B, {pct_time_cb:+.1f}% time — SUCCESS")
print(f"  ❌ Test C2 (integrated ctrl): {oh_c2b_e:+.1f}% energy vs B, {oh_c2b_t:+.1f}% time — REGRESSION")

print(f"\n  📊 Test B multi-rank data available: ranks {ranks_b}")
for r in ranks_b:
    n = len(test_b[r])
    me = stats(test_b[r], 0)[0]
    mt = stats(test_b[r], 1)[0]
    print(f"     N={r:>2}: {n} trials, avg energy={me:.0f}J, avg time={mt:.1f}s")

print(f"\nAll graphs saved to: {out_dir}")
