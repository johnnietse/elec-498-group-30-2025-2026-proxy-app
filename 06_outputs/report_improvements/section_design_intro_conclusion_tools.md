# Design Additions: Decision Matrix and Trade-Space Analysis

## Insert into Section 2.3 (Engineering Path to Final Design) — after the description of the three approaches

### Formal Design Alternative Evaluation

To systematically justify the final design selection, a weighted Pugh decision matrix was constructed evaluating the three candidate architectures against five engineering criteria. Each criterion was assigned a weight reflecting its importance to the project's success, informed by the Blueprint's specification priorities and the CAC's operational constraints.

**Table XX: Weighted Decision Matrix for Controller Architecture Selection**

| Criterion | Weight | Counter-Based Detection | Beta Algorithm | Hint-Based (Final) |
|---|---|---|---|---|
| Phase Detection Accuracy | 0.30 | 1 (3% measured) | 3 (indirect, ~40% est.) | 5 (~100% measured) |
| Runtime Overhead | 0.25 | 4 (low: read-only counters) | 1 (97.2% at N=2) | 4 (<3.21% worst case) |
| Implementation Complexity | 0.15 | 2 (counter correlation tuning) | 1 (PID + beta regression + freq emulation) | 5 (~500 LOC total) |
| Hardware Portability | 0.15 | 1 (Zen 1-specific IPC signatures) | 2 (requires /proc/stat + perf) | 4 (any Linux with cpufreq) |
| Maintainability | 0.15 | 2 (fragile thresholds) | 1 (complex state machine) | 5 (simple phase-to-policy map) |
| **Weighted Score** | | **2.15** | **1.70** | **4.65** |

**Scoring**: 1 = Poor, 2 = Below Average, 3 = Average, 4 = Good, 5 = Excellent.

The hint-based architecture scored 4.65/5.00 — more than double the Beta algorithm (1.70) and the counter-based approach (2.15). The dominant factor was detection accuracy (weight 0.30), where the hint-based approach's ~100% accuracy was decisive. The Beta algorithm scored lowest overall due to its catastrophic runtime overhead, which negated any potential energy benefit.

### Trade-Space Visualization

The design trade-space can be visualized by plotting the three alternatives on axes of Detection Accuracy versus Runtime Overhead (see Figure XX). An ideal controller occupies the upper-left quadrant (high accuracy, low overhead). The counter-based approach achieves low overhead but fails on accuracy. The Beta algorithm fails on both dimensions. Only the hint-based approach occupies the optimal region of the trade-space, confirming it as the Pareto-dominant design.

---

# Introduction Additions

## Insert at end of Section 1 (Introduction) — replace the final paragraph or add before it

### Quantitative Motivation (add to first paragraph)

**Replace**: "HPC systems consume energy on the scale of small cities"

**With**: "HPC systems consume energy on the scale of small cities — the Frontier supercomputer at Oak Ridge National Laboratory draws 22.7 MW, equivalent to powering approximately 18,000 residential homes [2]. The International Energy Agency reports that global data center electricity consumption reached 460 TWh in 2024, with HPC workloads comprising approximately 15% of this figure [1]. Within Canada, the Centre for Advanced Computing at Queen's University operates the Frontenac cluster as a shared national resource, where energy efficiency improvements benefit the entire Canadian research community."

### Contribution Statement (add as final paragraph of Section 1)

This report makes the following contributions to the field of energy-efficient high-performance computing:

1. **A user-level, phase-aware DVFS architecture** that achieves up to 17.53% energy savings on shared HPC infrastructure without requiring privileged system access — demonstrating that meaningful energy reductions are achievable within the operational constraints of multi-tenant supercomputing facilities.

2. **An empirical comparison of three controller architectures** (counter-based inference, adaptive beta algorithm, and application-injected hints), providing evidence-driven justification for the superiority of explicit phase communication over indirect inference methods on AMD Zen 1 microarchitectures.

3. **A statistically rigorous experimental evaluation** spanning 300 runs across 6 MPI rank configurations, with Welch's t-tests (p < 0.001 for all configurations) and Cohen's d effect sizes exceeding 15 standard deviations at operational scale, establishing the controller's effectiveness with high statistical confidence.

4. **An open-source, deployable implementation** consisting of approximately 500 lines of code (150 C++, 250 Python, 100 bash) that can be adopted on any Linux system with the standard cpufreq interface, lowering the barrier to entry for phase-aware power management in academic HPC environments.

---

# Conclusion Additions

## Insert into Section 6 (Conclusion and Recommendations) — add after existing content

### Commercialization Potential

The controller's minimal implementation footprint (~500 lines of code), zero hardware cost, and compatibility with standard Linux interfaces position it for potential commercialization as a lightweight plugin for HPC job schedulers. Integration with SLURM's Prolog/Epilog scripting framework or PBS Pro's hook mechanism would enable automatic deployment for any MPI application instrumented with phase hints. At an estimated market size of approximately 500 HPC centers worldwide, a commercial offering priced at $10,000–$50,000 per site license could address a $5M–$25M total addressable market. The open-source nature of the current implementation, however, suggests that a service-based model (consulting, integration, and support) may be more appropriate than proprietary licensing.

### Broader Societal and Cultural Impact

Widespread adoption of phase-aware DVFS in HPC environments would contribute to the growing cultural shift toward sustainable computing practices. As governments and institutions increasingly mandate carbon neutrality targets, tools that enable energy reduction without performance compromise will become essential infrastructure. However, potential adverse impacts must be acknowledged: over-reliance on automated power management systems could mask underlying hardware degradation or cooling failures that manifest as performance anomalies. To mitigate this risk, any production deployment should include monitoring dashboards (such as the one developed in this project) that alert operators to unexpected frequency patterns.

### Lessons Learned

Three categories of lessons emerged from this project:

- **Technical**: Counter-based phase detection on AMD Zen 1 is fundamentally limited by RAPL's 1 ms temporal granularity and overlapping IPC signatures between phases. Future implementations targeting newer architectures (Zen 4, Intel Sapphire Rapids) with higher-resolution performance monitoring units may revisit this approach.

- **Process**: The iterative, fail-fast methodology adopted from Petrini et al.'s "Case of the Missing Supercomputer Performance" proved invaluable. The two failed prototypes consumed approximately 12 person-weeks but generated the empirical evidence necessary to justify the final design. Early prototyping and rapid failure testing should be a standard practice in HPC systems research.

- **Professional**: Operating within institutional constraints (CAC's prohibition on system-level modifications) initially appeared to be a limitation but ultimately drove a more creative and portable solution. Constraints, when embraced rather than circumvented, can catalyze innovation.

---

# Tool Selection Justification Table

## Insert into Section 4.1.3 or as a new subsection

**Table XX: Tool Selection Rationale and Limitation Assessment**

| Tool | Selection Rationale | Alternatives Considered | Known Limitations | Impact on Results |
|---|---|---|---|---|
| RAPL (`energy-pkg`) | Hardware-integrated; no external instrumentation required; validated <5% accuracy for server systems [8][9] | External wall-power meter (unavailable on shared node); PAPI library | 1 ms update granularity; measures package-level power only (not per-core) | Granularity insufficient for sub-ms phase detection → drove pivot to hint-based approach |
| `perf stat` | Kernel-integrated; low overhead for aggregate measurements | `likwid` (not installed); Intel VTune (not available on AMD) | fork()/execve() overhead prohibitive for continuous monitoring | High system call overhead when used in Beta prototype → contributed to 97.2% runtime increase |
| Python 3 + `ctypes` | Rapid prototyping; native `mmap` support; `ctypes` enables direct shared-memory struct access | C++ monitor (lower overhead but longer development time) | GIL prevents true parallel execution; higher per-iteration latency than C | Necessitated dedicated monitor core to avoid GIL-induced contention with MPI ranks |
| OpenMPI `mpirun` | Pre-installed on Frontenac; supports `--bind-to core` and `--map-by core` binding | MPICH; Intel MPI (not available) | Process binding syntax not portable across MPI implementations | Core binding ensured deterministic rank-to-core mapping, critical for per-core DVFS |
| `matplotlib` | Standard Python visualization library; publication-quality output | Plotly (interactive but heavier); gnuplot | Limited 3D/interactive capabilities | Sufficient for all 21 figures; consistent styling across all visualizations |
| SciPy `ttest_ind` | Welch's t-test implementation matches Blueprint's statistical framework | R (not installed); statsmodels | Assumes approximately normal distributions | Normality assumption validated by symmetric box-and-whisker distributions (Figure 13) |
