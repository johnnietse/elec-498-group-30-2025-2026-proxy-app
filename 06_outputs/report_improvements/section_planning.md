# Project Planning, Resource Allocation, and Adaptive Management

## Timeline and Project Phases

The project spanned approximately 32 weeks (September 2025 to April 2026), divided into five major phases. The timeline below documents both the planned and actual progression, including two significant design pivots that required adaptive replanning.

| Phase | Planned Duration | Actual Duration | Key Activities |
|---|---|---|---|
| **Phase 1: Literature Review & Requirements** | Weeks 1–4 (Sep 2025) | Weeks 1–5 | Survey of CoPPer, EAR, Adagio, ASCI Q; Blueprint specification development; CAC node allocation request |
| **Phase 2: Counter-Based Prototype** | Weeks 5–10 (Oct–Nov 2025) | Weeks 6–12 | Implementation of IPC/cache-miss phase classifier; RAPL-based inference prototype; **Pivot Point 1**: Achieved only 3% accuracy → abandoned |
| **Phase 3: Beta Algorithm Prototype** | Weeks 11–16 (Nov–Jan 2026) | Weeks 13–18 | Implementation of Hsu's beta-adaptation algorithm; per-core utilization scanning via `/proc/stat`; **Pivot Point 2**: 97.2% runtime increase at N=2 → abandoned |
| **Phase 4: Final Hint-Based Design** | Weeks 17–24 (Jan–Mar 2026) | Weeks 19–26 | miniMD shared-memory instrumentation; Python monitor development; bash orchestration; 300-run experimental campaign (111.6 hours of dedicated node time) |
| **Phase 5: Analysis & Reporting** | Weeks 25–32 (Mar–Apr 2026) | Weeks 27–32 | Statistical analysis; figure generation; final report writing; dashboard development |

### Adaptive Replanning

The original project plan allocated 6 weeks to Phase 2 (counter-based detection) and assumed successful completion before proceeding to integration testing. When Phase 2 produced only 3% classification accuracy (far below the 95% target), the team convened a design review and decided to pivot to the Beta algorithm approach, extending the prototype phase by 2 weeks. When the Beta algorithm also failed (introducing catastrophic runtime overhead), a second design review led to the adoption of application-injected hints — a fundamentally different architecture that required restarting the implementation from a new design basis.

This adaptive replanning added approximately 6 weeks to the development timeline but ultimately produced a superior solution. The key lesson was that early prototyping and rapid failure testing saved significant project time compared to a strategy of committing fully to an unvalidated approach. The two failed prototypes consumed approximately 12 person-weeks of effort but generated critical empirical evidence (3% accuracy, 97.2% overhead) that directly informed the final design's success criteria.

## Resource Allocation

### Personnel Effort Distribution

| Team Member | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Phase 5 | Total Hours (est.) |
|---|---|---|---|---|---|---|
| Johnnie Tse | Literature review, Blueprint | Counter prototype | Beta prototype, miniMD instrumentation | Monitor development, testing | Analysis, figures, report | ~200 hrs |
| Gia Lee | Requirements analysis | Counter prototype | Beta prototype | Testing campaign | Report writing | ~200 hrs |
| Zane Prance | CAC coordination | Infrastructure setup | Dashboard development | Bash orchestration, testing | Dashboard finalization | ~200 hrs |
| Valerie So | Literature review | Data pipeline | Analysis scripts | Data collection | Statistical analysis, report | ~200 hrs |

### Computational Resource Allocation

- **Dedicated node**: frnt115 on CAC Frontenac cluster (exclusive reservation via SLURM)
- **Experimental campaign**: 300 runs × 1,340 s average = **111.6 hours** of continuous node time
- **Core allocation per run**: 26 worker cores + 1 monitor core + 1 reserved core + 4 OS cores = 32 cores total
- **Storage**: ~2 GB for CSV logs, ~300 MB for checkpoint binaries (excluded from Git via `.gitignore`)

## Risk Register

The following risk register documents the risks identified during the project planning phase, their assessed probability and impact, the mitigation strategies adopted, and the actual outcomes observed.

| # | Risk | Probability | Impact | Mitigation Strategy | Actual Outcome |
|---|---|---|---|---|---|
| R1 | Counter-based phase detection achieves insufficient accuracy | High | Critical | Blueprint Section 2.4.2 identifies code-level instrumentation as fallback | **Occurred** (3% accuracy). Pivoted to application hints per fallback strategy. |
| R2 | Beta algorithm introduces excessive runtime overhead | Medium | High | Benchmark prototype before committing to full experimental campaign | **Occurred** (97.2% overhead at N=2). Abandoned after 3-week evaluation. |
| R3 | RAPL energy measurement accuracy insufficient for statistical validation | Low | Medium | Cross-validate with multiple runs; use Welch's t-test to assess significance | **Not occurred**. CV < 2% across all configurations; all results statistically significant. |
| R4 | SLURM scheduling conflicts prevent dedicated node access | Medium | Medium | Request exclusive node reservation; schedule experiments during off-peak hours | **Mitigated**. Exclusive reservation on frnt115 eliminated contention. |
| R5 | Shared memory race conditions corrupt phase hints | Low | High | Implement lock-free sequence-number validation protocol | **Not occurred**. Zero corrupted reads observed across 300 runs. |
| R6 | Controller leaves CPU governors in incorrect state after crash | Medium | High | Register cleanup handlers via bash `trap`; verify governor state before each run | **Mitigated**. Cleanup handler tested and verified during development. |
| R7 | 50-page report limit exceeded due to extensive data | Medium | Low | Prioritize key figures in body; use Appendix for supplementary tables | **Mitigated**. Final report structured within page limit. |

## Budget Reconciliation

As documented in Table 2 of the report, the project incurred zero direct hardware procurement costs. The effective budget consisted entirely of personnel time (estimated at 800 person-hours across four team members) and computational resource allocation (111.6 hours of dedicated cluster time, provided at no cost by CAC as part of the academic research agreement). No software licenses were purchased; all tools (Python, OpenMPI, matplotlib, Linux perf) are open-source or pre-installed on the cluster. The total effective project cost, valued at a graduate research assistant rate of $25/hour, was approximately $20,000 in personnel effort — fully funded through the academic program.
