#!/usr/bin/env python3
"""
Complete analysis: A, B, C (comm_freq_controller), C2 (integrated_freq_controller)
All N=16, 1 trial each. Frequencies fixed to 2400 MHz (clamped to 2000 by HW).
"""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

out_dir = os.path.join(os.path.dirname(__file__), 'graphs')
os.makedirs(out_dir, exist_ok=True)

plt.rcParams.update({
    'font.size': 11, 'axes.titlesize': 13, 'axes.labelsize': 11,
    'figure.figsize': (12, 6), 'figure.dpi': 150,
    'savefig.bbox': 'tight', 'savefig.dpi': 150,
})

# ============================================================
# DATA — All N=16, 1 trial
# ============================================================
idle_avg = 64.64  # W

data = {
    'Test A\n(Baseline)': {
        'energy': 7299.031, 't_total': 67.887, 't_force': 29.394,
        't_neigh': 4.756, 't_comm': 0.797, 't_other': 32.940,
        'perf': 12356683, 'io_dur': 31.46, 'comm_dur': 0,
        'color': '#4C72B0',
    },
    'Test B\n(Comm ON)': {
        'energy': 12877.431, 't_total': 67.955, 't_force': 29.407,
        't_neigh': 4.755, 't_comm': 0.817, 't_other': 32.976,
        'perf': 12344394, 'io_dur': 31.46, 'comm_dur': 0.027,
        'color': '#DD8452',
    },
    'Test C\n(comm ctrl)': {
        'energy': 11093.842, 't_total': 68.218, 't_force': 29.405,
        't_neigh': 4.761, 't_comm': 0.844, 't_other': 33.208,
        'perf': 12296807, 'io_dur': 31.41, 'comm_dur': 0.049,
        'transitions': 3, 'color': '#55A868',
    },
    'Test C2\n(integ ctrl)': {
        'energy': 12933.609, 't_total': 106.763, 't_force': 45.000,
        't_neigh': 7.889, 't_comm': 20.511, 't_other': 33.363,
        'perf': 7857247, 'io_dur': 31.51, 'comm_dur': 0.039,
        'transitions': 3, 'color': '#C44E52',
    },
}

labels = list(data.keys())
colors = [data[k]['color'] for k in labels]
tests = [data[k] for k in labels]

walls = [t['t_total'] + t['io_dur'] + t.get('comm_dur', 0) for t in tests]
powers = [t['energy'] / w for t, w in zip(tests, walls)]

# ============================================================
# GRAPH 1: Energy
# ============================================================
fig, ax = plt.subplots()
energies = [t['energy'] for t in tests]
bars = ax.bar(labels, energies, color=colors, edgecolor='black', linewidth=0.5, width=0.6)
for bar, val in zip(bars, energies):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 150,
            f'{val:,.0f} J', ha='center', va='bottom', fontweight='bold', fontsize=10)
ax.set_ylabel('Total Energy (J)')
ax.set_title('Graph 1: Total Energy (N=16, 1 Trial)')
ax.set_ylim(0, max(energies) * 1.12)
ax.grid(axis='y', alpha=0.3)
# Savings annotation
s_cb = (data['Test B\n(Comm ON)']['energy'] - data['Test C\n(comm ctrl)']['energy']) / data['Test B\n(Comm ON)']['energy'] * 100
ax.annotate(f'−{s_cb:.0f}% vs B', xy=(2, data['Test C\n(comm ctrl)']['energy']),
            xytext=(2, data['Test C\n(comm ctrl)']['energy'] - 1200),
            fontsize=10, color='green', fontweight='bold', ha='center')
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'graph1_energy_comparison.png'))
plt.close()

# ============================================================
# GRAPH 2: Time
# ============================================================
fig, ax = plt.subplots()
times = [t['t_total'] for t in tests]
bars = ax.bar(labels, times, color=colors, edgecolor='black', linewidth=0.5, width=0.6)
for bar, val in zip(bars, times):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.8,
            f'{val:.1f}s', ha='center', va='bottom', fontweight='bold', fontsize=10)
ax.set_ylabel('Execution Time (s)')
ax.set_title('Graph 2: Execution Time (N=16, 1 Trial)')
ax.set_ylim(0, max(times) * 1.12)
ax.grid(axis='y', alpha=0.3)
ax.annotate('+57% slower\n(β-adapt)', xy=(3, tests[3]['t_total']),
            xytext=(2.5, tests[3]['t_total'] * 0.85),
            fontsize=10, color='red', fontweight='bold',
            arrowprops=dict(arrowstyle='->', color='red'))
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'graph2_time_comparison.png'))
plt.close()

# ============================================================
# GRAPH 4: Average Power
# ============================================================
fig, ax = plt.subplots()
bars = ax.bar(labels, powers, color=colors, edgecolor='black', linewidth=0.5, width=0.6)
for bar, val in zip(bars, powers):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
            f'{val:.1f} W', ha='center', va='bottom', fontweight='bold', fontsize=10)
ax.axhline(y=idle_avg, color='gray', linestyle='--', linewidth=1,
           label=f'Idle ({idle_avg:.1f} W)')
ax.set_ylabel('Average Power (W)')
ax.set_title('Graph 4: Average Power (N=16, 1 Trial)')
ax.set_ylim(0, max(powers) * 1.25)
ax.legend()
ax.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'graph4_avg_power.png'))
plt.close()

# ============================================================
# GRAPH 10: Performance
# ============================================================
fig, ax = plt.subplots()
perfs = [t['perf'] for t in tests]
bars = ax.bar(labels, [p/1e6 for p in perfs], color=colors, edgecolor='black', linewidth=0.5, width=0.6)
for bar, val in zip(bars, perfs):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.08,
            f'{val/1e6:.2f}M', ha='center', va='bottom', fontweight='bold', fontsize=10)
ax.set_ylabel('Performance (M atom-steps/s)')
ax.set_title('Graph 10: Performance (N=16, 1 Trial)')
ax.set_ylim(0, max(perfs)/1e6 * 1.15)
ax.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'graph10_performance.png'))
plt.close()

# ============================================================
# GRAPH 14: Stacked Time Breakdown
# ============================================================
fig, ax = plt.subplots(figsize=(12, 7))
x = np.arange(4)
w = 0.55
comps = ['t_force', 't_neigh', 't_comm', 't_other']
comp_colors = ['#4C72B0', '#55A868', '#C44E52', '#8172B2']
comp_labels = ['t_force', 't_neigh', 't_comm (halo exchange)', 't_other (I/O + comm phase)']
bottoms = np.zeros(4)
for comp, col, lab in zip(comps, comp_colors, comp_labels):
    vals = [t[comp] for t in tests]
    ax.bar(x, vals, w, bottom=bottoms, label=lab, color=col)
    bottoms += vals

ax.set_xticks(x)
ax.set_xticklabels(['Test A', 'Test B', 'Test C\n(comm)', 'Test C2\n(integrated)'])
ax.set_ylabel('Time (s)')
ax.set_title('Graph 14: Time Breakdown — Where the slowdown comes from')
ax.legend(loc='upper left')
ax.grid(axis='y', alpha=0.3)
# Annotate C2 issues
ax.annotate('t_force +53%\nt_comm 25×',
            xy=(3, 80), fontsize=10, color='red', fontweight='bold', ha='center')
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'graph14_time_breakdown.png'))
plt.close()

# ============================================================
# GRAPH: Per-Component Deep Dive
# ============================================================
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
component_info = [
    ('t_force', 'Force Computation (CPU-bound)', axes[0,0]),
    ('t_neigh', 'Neighbor List Build (CPU-bound)', axes[0,1]),
    ('t_comm', 'MPI Halo Exchange (sync-sensitive)', axes[1,0]),
    ('t_other', 'Other (I/O, setup, comm phase)', axes[1,1]),
]
for comp, title, ax in component_info:
    vals = [t[comp] for t in tests]
    bars = ax.bar(labels, vals, color=colors, edgecolor='black', linewidth=0.5, width=0.55)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(vals)*0.02,
                f'{val:.1f}s', ha='center', va='bottom', fontsize=9, fontweight='bold')
    ax.set_ylabel('Time (s)')
    ax.set_title(title)
    ax.grid(axis='y', alpha=0.3)

plt.suptitle('Per-Component Breakdown (N=16)', fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'graph_component_breakdown.png'))
plt.close()

# ============================================================
# GRAPH 11: Energy Efficiency
# ============================================================
fig, ax = plt.subplots()
eff = [t['perf'] / p for t, p in zip(tests, powers)]
bars = ax.bar(labels, [e/1e6 for e in eff], color=colors, edgecolor='black', linewidth=0.5, width=0.6)
for bar, val in zip(bars, eff):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.002,
            f'{val/1e6:.3f}M', ha='center', va='bottom', fontweight='bold', fontsize=10)
ax.set_ylabel('Efficiency (M atom-steps/s per W)')
ax.set_title('Graph 11: Energy Efficiency (Perf / Avg Power)')
ax.set_ylim(0, max(eff)/1e6 * 1.15)
ax.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'graph11_energy_efficiency.png'))
plt.close()

# ============================================================
# GRAPH 15: Dynamic vs Idle Energy
# ============================================================
fig, ax = plt.subplots()
idle_energies = [idle_avg * w for w in walls]
dynamic_energies = [t['energy'] - ie for t, ie in zip(tests, idle_energies)]
x = np.arange(4)
b1 = ax.bar(x, dynamic_energies, 0.5, label='Dynamic Energy',
            color=colors, edgecolor='black', linewidth=0.5)
b2 = ax.bar(x, idle_energies, 0.5, bottom=dynamic_energies,
            label='Idle Energy', color='lightgray', edgecolor='gray', linewidth=0.5)
ax.set_xticks(x)
ax.set_xticklabels(['Test A', 'Test B', 'Test C', 'Test C2'])
ax.set_ylabel('Energy (J)')
ax.set_title('Graph 15: Dynamic vs Idle Energy')
ax.legend()
ax.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'graph15_dynamic_vs_idle.png'))
plt.close()

# ============================================================
# GRAPH 16: Phase Timelines (side by side)
# ============================================================
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

# comm_freq_controller
phases = ['COMPUTE (2.0GHz)', 'I/O (1.2GHz)', 'COMM', 'COMPUTE (2.0GHz)']
dur_c = [68.218/2, 31.41, 0.049, 68.218/2]
ax1.barh(phases, dur_c, color=['#55A868','#8172B2','#C44E52','#55A868'],
         edgecolor='black', linewidth=0.5, height=0.6)
for i, d in enumerate(dur_c):
    if d > 1:
        ax1.text(d/2, i, f'{d:.1f}s', ha='center', va='center', fontsize=10,
                 fontweight='bold', color='white')
    else:
        ax1.text(d+0.3, i, f'{d:.3f}s', ha='left', va='center', fontsize=9)
ax1.set_title('comm_freq_controller — t_total: 68.2s ✅', fontweight='bold')
ax1.set_xlabel('Duration (s)')

# integrated_freq_controller
phases2 = ['COMPUTE (β-adapt)', 'I/O (1.2GHz)', 'COMM', 'COMPUTE (β-adapt)']
dur_c2 = [147.408, 31.449, 0.050, 106.763 - 147.408 - 31.449 - 0.050]
# Fix: compute durations from the controller perspective
# Controller ran for 147.4s before IO - but that includes pre-sim wait
# Use the actual timing from PERF: first 50 steps + last 50 steps + IO + comm
compute_half = (tests[3]['t_total'] - tests[3]['t_other']) / 2  # approximate
dur_c2 = [compute_half, 31.51, 0.039, compute_half]
ax2.barh(phases2, dur_c2, color=['#C44E52','#8172B2','#DD8452','#C44E52'],
         edgecolor='black', linewidth=0.5, height=0.6)
for i, d in enumerate(dur_c2):
    if d > 1:
        ax2.text(d/2, i, f'{d:.1f}s', ha='center', va='center', fontsize=10,
                 fontweight='bold', color='white')
    else:
        ax2.text(d+0.3, i, f'{d:.3f}s', ha='left', va='center', fontsize=9)
ax2.set_title('integrated_freq_controller — t_total: 106.8s ❌ (+57%)', fontweight='bold')
ax2.set_xlabel('Duration (s)')

plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'graph16_phase_timeline.png'))
plt.close()

# ============================================================
# GRAPH 8/9: Overhead comparisons
# ============================================================
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

# B vs A overhead
oh_ba = (tests[1]['t_total'] - tests[0]['t_total']) / tests[0]['t_total'] * 100
ax1.bar(['Comm Phase\nOverhead (B-A)'], [oh_ba], color='#DD8452', edgecolor='black', width=0.35)
ax1.text(0, oh_ba + 0.01, f'{oh_ba:.2f}%', ha='center', fontweight='bold', fontsize=12)
ax1.set_ylabel('Time Overhead (%)')
ax1.set_title('Graph 8: Comm Phase Overhead')
ax1.set_ylim(0, max(1, oh_ba * 5))
ax1.grid(axis='y', alpha=0.3)

# C vs B and C2 vs B
oh_cb = (tests[2]['t_total'] - tests[1]['t_total']) / tests[1]['t_total'] * 100
oh_c2b = (tests[3]['t_total'] - tests[1]['t_total']) / tests[1]['t_total'] * 100
bars = ax2.bar(['C (comm)\nvs B', 'C2 (integ)\nvs B'], [oh_cb, oh_c2b],
               color=['#55A868', '#C44E52'], edgecolor='black', width=0.45)
for bar, val in zip(bars, [oh_cb, oh_c2b]):
    ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
             f'{val:+.1f}%', ha='center', fontweight='bold', fontsize=11)
ax2.set_ylabel('Time Overhead (%)')
ax2.set_title('Graph 9: Controller Overhead vs Test B')
ax2.grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.savefig(os.path.join(out_dir, 'graph8_9_overhead.png'))
plt.close()

# ============================================================
# SUMMARY
# ============================================================
print("=" * 85)
print("FULL RESULTS — A, B, C (comm ctrl), C2 (integrated ctrl) — N=16, 1 trial")
print("=" * 85)

print(f"\n{'Metric':<20} {'Test A':<13} {'Test B':<13} {'C (comm)':<13} {'C2 (integ)':<13} {'C vs B':<8} {'C2 vs B'}")
print(f"{'-'*20} {'-'*13} {'-'*13} {'-'*13} {'-'*13} {'-'*8} {'-'*8}")
for m, k in [('Energy (J)', 'energy'), ('t_total (s)', 't_total'), ('t_force (s)', 't_force'),
             ('t_neigh (s)', 't_neigh'), ('t_comm (s)', 't_comm'), ('t_other (s)', 't_other')]:
    va, vb, vc, vc2 = tests[0][k], tests[1][k], tests[2][k], tests[3][k]
    cb = f"{(vc-vb)/vb*100:+.0f}%"
    c2b = f"{(vc2-vb)/vb*100:+.0f}%"
    if k == 'energy':
        print(f"  {m:<18} {va:<13,.0f} {vb:<13,.0f} {vc:<13,.0f} {vc2:<13,.0f} {cb:<8} {c2b}")
    else:
        print(f"  {m:<18} {va:<13.2f} {vb:<13.2f} {vc:<13.2f} {vc2:<13.2f} {cb:<8} {c2b}")
print(f"  {'Performance':<18} {tests[0]['perf']:<13,} {tests[1]['perf']:<13,} {tests[2]['perf']:<13,} {tests[3]['perf']:<13,}")
print(f"  {'Avg Power (W)':<18} {powers[0]:<13.1f} {powers[1]:<13.1f} {powers[2]:<13.1f} {powers[3]:<13.1f}")

print(f"\n  ✅ Test C (comm ctrl): −14% energy vs B, +0.4% time, no perf loss")
print(f"  ❌ Test C2 (integrated): +0.4% energy vs B, +57% time, −36% perf loss")

print(f"\n{'='*85}")
print("BUGS IN TEST C2 RUN")
print("="*85)
print("""
  🐛 Bug 1: Transitions shows 0 in CSV
     Root cause: grep "Phase transition:" doesn't match integrated's "PHASE:" format
     Fix: Use grep -cE "(Phase transition:|PHASE:)" for C2 logs
     Actual transitions: 3 (confirmed in controller log)

  🐛 Bug 2: CSV has extra "0" on separate line
     The CSV shows:
       1,16,12933.609,...,0
       0
     The "0" on the 2nd line is from TRANSITIONS variable echoed separately.
     This is a cosmetic issue — the CSV parser will skip it.
""")

print(f"\nAll graphs saved to: {out_dir}")
