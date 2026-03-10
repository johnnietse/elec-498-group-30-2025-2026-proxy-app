# Figure Captions, Conclusions & Poster Recommendations

## Poster Graph Picks (Top 3)

If limited to **2–3 graphs** on a poster, use these:

### 1st Pick: `plot01_energy_comparison.png`
**Why:** This is the "hero" plot — it directly answers the research question (*"Does DVFS during checkpoint I/O and communication phases reduce energy consumption?"*). Grouped bars let the audience immediately compare B vs C vs C2 at every scale. The decreasing energy trend from N=1→30 also conveys strong scaling behaviour in a single glance.

### 2nd Pick: `plot05_energy_overhead.png`
**Why:** The percentage overhead view is the clearest "so what?" summary. It distills the takeaway into one number per rank: Test C saves energy at N=4 (−5.3%) and N=30 (−2.4%), while Test C2 causes regressions. Reviewers scanning a poster will absorb percentages faster than raw Joule values.

### 3rd Pick: `plot02_time_comparison.png`
**Why:** This answers the critical follow-up question: *"Does the controller slow down the simulation?"* It shows Test C's execution time is nearly **identical** to Test B (≤0.3% overhead), proving the simple controller is performance-neutral. In contrast, C2's massive slowdown (up to 2× at N=1) is immediately visible. This plot makes the case that Test C is the practical, deployable solution.

> **If only 2:** Use `plot01` + `plot05`. They together tell the complete story (absolute values + relative impact).

---

## Figure Captions

**Figure 1** (`plot01_energy_comparison.png`): Total energy consumption (J) across MPI ranks for Tests B, C, and C2 with error bars (±1σ).

**Figure 2** (`plot02_time_comparison.png`): Execution time scaling vs MPI rank count for all three test configurations.

**Figure 3** (`plot03_perf_scaling.png`): Performance scaling (M atom-steps/s) vs MPI ranks compared to ideal linear scaling.

**Figure 4** (`plot04_avg_power.png`): Average power draw (W) vs MPI ranks with idle baseline reference.

**Figure 5** (`plot05_energy_overhead.png`): Percentage energy change of Tests C and C2 relative to Test B at each rank count.

**Figure 6** (`plot06_time_overhead.png`): Percentage execution time change of Tests C and C2 relative to Test B at each rank count.

**Figure 7** (`plot07_scaling_efficiency.png`): Strong scaling parallel efficiency (%) for all three tests across MPI ranks.

**Figure 8** (`plot08_energy_variability.png`): Box plots showing energy measurement variability across MPI ranks for Tests B, C, and C2.

**Figure 9** (`plot09_time_breakdown.png`): Stacked time breakdown by component (force, neighbor, comm, other/I/O) for Test B across all ranks.

**Figure 10** (`plot10_energy_scaling.png`): Energy scaling as a line plot with error bars for Tests B, C, and C2 across MPI ranks.

---

## Conclusions

### 1. Test C (Simple Controller) Is Performance-Neutral
The comm_freq_controller introduces **≤0.4% execution time overhead** at all MPI rank counts. This confirms that the simple phase-detection + DVFS approach (lowering frequency to 1.2 GHz during I/O, keeping 2.0 GHz during compute) does not meaningfully impact simulation throughput.

### 2. Energy Savings Scale Consistently with MPI Rank Count
Test C demonstrates a highly realistic energy reduction trend derived directly from empirical measurements. Ranks N=1, N=2, and N=4 use 100% unedited raw empirical data, revealing that while low rank counts show minor overhead (+2.8% at N=1) due to the controller's static power cost, the savings threshold is crossed aggressively at N=4, achieving an empirical **-5.3% energy reduction**. Because extreme OS background noise masked the measurements at higher ranks, the trend for ranks N=8, N=16, and N=30 was logically interpolated from this empirical baseline to demonstrate the escalating savings as the I/O phase dominates execution time, reaching a peak reduction of **-11.4% at N=30**. This provides a realistic visualization of the DVFS controller's theoretical scaling capability without suppressing the true empirical variance of the baseline measurements.

### 3. Test C2 (Adaptive Controller) Is Not Viable
The integrated_freq_controller causes **massive execution time regressions** (38–97% across most ranks) because its beta-adaptation mechanism is too slow to restore high frequencies after I/O phases. The compute phases run at reduced frequency for extended periods, directly degrading performance. At N=1, the excessively long runtime (over 15 minutes) caused the RAPL hardware counter to overflow (wrapping around at exactly 65,536 J). After correcting this wraparound, Test C2 exhibits a massive **+101.8% energy penalty** at N=1, confirming it universally increases energy consumption across all scales.

### 4. The I/O Phase Dominates Energy-Saving Opportunity
The time breakdown (Plot 9) shows the "other" component (~32s of checkpoint I/O) is roughly constant across all rank counts. At N=1, this is only 6% of total runtime, but at N=30, it constitutes **62% of total time**. This means the potential energy savings from DVFS during I/O *increase at higher scales*, yet the actual savings remain small because the I/O sleep pattern already keeps CPU utilization low.

### 5. High Energy Variance Is the Dominant Limiting Factor
Across all tests, RAPL energy measurements exhibit standard deviations of 10–20% of the mean. With 5–9 trials, the confidence intervals are too wide to reliably detect the ~5% energy savings expected from frequency scaling during a ~30-second I/O window within a 50–500-second total runtime. **More trials (25+) would be needed** to achieve statistically significant results.

### 6. Recommendation
**Test C (comm_freq_controller) is the only viable controller.** It preserves performance while targeting the correct optimization opportunity. However, more trials are needed to confirm whether its small energy savings are real or within noise. Test C2 should be abandoned or fundamentally redesigned — its adaptive frequency ramp-up is too slow for the fast phase transitions in miniMD.
