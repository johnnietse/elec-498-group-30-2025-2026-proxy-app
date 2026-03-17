import re

with open('generate_b_vs_c_plots.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Remove from all tests
text = text.replace("    ('Test C2', test_c2, C_C2),\n", "")

# Fix Plot 5
p5_pattern = r'# PLOT 5: Energy Overhead.*?print\("  \[5/10\] plot05_energy_overhead\.png"\)'
p5_replacement = """# PLOT 5: Energy Overhead — C vs B (% change)
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
print("  [5/10] plot05_energy_overhead.png")"""
text = re.sub(p5_pattern, p5_replacement, text, flags=re.DOTALL)

# Fix Plot 6
p6_pattern = r'# PLOT 6: Time Overhead.*?print\("  \[6/10\] plot06_time_overhead\.png"\)'
p6_replacement = """# PLOT 6: Time Overhead — C vs B (%)
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
print("  [6/10] plot06_time_overhead.png")"""
text = re.sub(p6_pattern, p6_replacement, text, flags=re.DOTALL)


# Fix Summary Table at bottom
summary_pattern = r'print\(f"\\n  --- Energy Overhead vs Test B ---"\).*?print\(f"\\nAll 10 plots saved to: \{out_dir\}"\)'
summary_replacement = """print(f"\\\\n  --- Energy Overhead vs Test B ---")
print(f"  {'Ranks':<7} {'C vs B':<14}")
print("  " + "-" * 20)
for r in ranks:
    eb = stats(test_b[r], 0)[0]
    ec = stats(test_c[r], 0)[0]
    pct_c  = (ec - eb) / eb * 100
    print(f"  N={r:<4} {pct_c:>+8.1f}%")

print(f"\\\\nAll 10 plots saved to: {out_dir}")"""
text = re.sub(summary_pattern, summary_replacement, text, flags=re.DOTALL)


# Fix Plot 8 (3 charts to 2 charts)
p8_pattern = r'fig, axes = plt\.subplots\(1, 3, figsize=\(18, 6\), sharey=True\).*?# ============================================================.*?# PLOT 9'
p8_replacement = """fig, axes = plt.subplots(1, 2, figsize=(12, 6), sharey=True)

for ax, (label, data, color) in zip(axes, all_tests):
    energy_data = [[d[0] for d in data[r]] for r in ranks]
    bp = ax.boxplot(energy_data, positions=range(len(ranks)), widths=0.5,
                    patch_artist=True,
                    tick_labels=[f'N={r}\\\\n({len(data[r])}t)' for r in ranks])
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
# PLOT 9"""
text = re.sub(p8_pattern, p8_replacement, text, flags=re.DOTALL)


# Fix Ideal Linear in Plot 3
perf_pattern = r'perf_b1 = stats\(test_b\[1\], 6\).*?ideal = \[perf_b1 \* r for r in ranks\]'
perf_replacement = """perf_b2 = stats(test_b[2], 6)[0]/1e6
ideal = [(perf_b2 / 2) * r for r in ranks]"""
text = re.sub(perf_pattern, perf_replacement, text, flags=re.DOTALL)

# Fix Ideal Linear in Plot 7
perf7_pattern = r'perf_1 = stats\(data\[1\], 6\)\[0\].*?effs = \[\(stats\(data\[r\], 6\)\[0\] / \(perf_1 \* r\)\) \* 100 for r in ranks\]'
perf7_replacement = """perf_2 = stats(data[2], 6)[0]
    effs = [(stats(data[r], 6)[0] / (perf_2 * (r / 2))) * 100 for r in ranks]"""
text = re.sub(perf7_pattern, perf7_replacement, text, flags=re.DOTALL)

with open('generate_b_vs_c_plots.py', 'w', encoding='utf-8') as f:
    f.write(text)
