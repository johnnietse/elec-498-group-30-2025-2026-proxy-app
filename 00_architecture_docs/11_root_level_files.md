# 11_root_level_files.md — Root-Level Files Documentation

**Scope:** Documentation of every file located at the root of the repository (not inside any numbered directory).

---

## Root Directory Listing

```
ELEC_498_All_directories_and_branches_folder_for_2026_02_15/
├── README.md                    (1,984 bytes · 33 lines)
├── .gitignore                   (112 bytes · 13 lines)
├── reorganize_workspace.ps1     (15,722 bytes · 348 lines)
├── large_files.txt              (356 bytes)
├── push_log.txt                 (2,194 bytes)
├── .git/                        (Git metadata)
├── .venv/                       (Python virtual environment)
└── johnnie-comm-phase/          (Active development branch)
```

---

## File-by-File Documentation

### `README.md` — Project Overview

| Attribute | Value |
|-----------|-------|
| Size | 1,984 bytes (33 lines) |
| Format | Markdown |
| Purpose | Top-level project overview and directory guide |

**Content Summary:**
- Project title: "miniMD Phase-Aware DVFS Optimization"
- Subtitle: "Sustainable Supercomputing Using Power Controls to Maximize Performance and Minimize Energy Usage"
- Team members: Johnnie Tse, Gia Lee, Zane Prance, Valerie So
- Repository structure table (8 directories with purposes)
- Quick-start pointers to key files

---

### `.gitignore` — Version Control Exclusions

| Attribute | Value |
|-----------|-------|
| Size | 112 bytes (13 lines) |
| Format | Git ignore patterns |

| Pattern | Purpose |
|---------|---------|
| `.venv/` | Python virtual environment |
| `__pycache__/` | Python bytecode cache |
| `*.pyc` | Compiled Python files |
| `.pytest_cache/` | Pytest cache |
| `*.log` | Log files |
| `*.bin` | Binary files (checkpoint data) |
| `*.pt` | PyTorch model files |
| `*.h5` | HDF5 data files |
| `*.npy` | NumPy array files |
| `*checkpoint*/` | Checkpoint directories |
| `large_files.txt` | Large file registry (generated) |
| `push_log.txt` | Push operation log (generated) |

**Key Exclusion:** `*.bin` prevents the 316 MB checkpoint file (`checkpoint_step00000000_rank00000.bin` in `gia_scaling_io/`) from being committed to Git.

---

### `reorganize_workspace.ps1` — Workspace Migration Script

| Attribute | Value |
|-----------|-------|
| Size | 15,722 bytes (348 lines) |
| Language | PowerShell |
| Purpose | Transforms the flat, branch-based workspace into the professional numbered directory structure |
| Idempotency | Partially — checks for existence before creating directories, but file moves are one-shot |
| Root Path | `c:\Users\Johnnie\Documents\ELEC_498_All_directories_and_branches_folder_for_2026_02_15` |

#### Execution Phases

| Phase | Lines | Purpose | Actions |
|-------|-------|---------|---------|
| **Phase 1** | 12–47 | Create Directory Skeleton | Creates all `01_docs/` through `08_test_gui/` directories and subdirectories |
| **Phase 2** | 49–106 | Move Loose Root Files | Moves reports → `01_docs/reports/`, raw results → `05_data/`, scripts → `03_scripts/` |
| **Phase 3** | 108–133 | Move Final Plots | Moves `fig*` files → `06_outputs/final_figures/`, `plot*` → `06_outputs/supplementary_plots/` |
| **Phase 4** | 135–160 | Archive Development Branches | Moves all 8 development branches → `07_archive/` with standardized naming |
| **Phase 5** | 162–229 | Copy Final Source into `02_src/` | Copies curated files from archived branches to production locations |
| **Phase 6** | 231–319 | Copy Configs, Scripts, Data, GUI | Copies configs, batch tests, CSV data, Excel files, GUI tools, and guides |
| **Phase 7** | 321–333 | Cleanup | Removes duplicate script references |

#### Branch Rename Mapping (Phase 4)

| Original Branch Name | Archive Directory |
|---------------------|-------------------|
| `johnnie-branch` | `johnnie_serial_memory_phase` |
| `johnnie-comm-phase` | `johnnie_comm_phase` |
| `gia-Final` | `gia_final` |
| `gia-scaling-io` | `gia_scaling_io` |
| `zane_mpi_comm` | `zane_mpi_comm` |
| `zane_prototype` | `zane_prototype` |
| `val_testing` | `val_testing` |
| `elec-498-group-30-2025-2026-proxy-app` | `main_repo` |

---

### `large_files.txt` — Large File Registry

| Attribute | Value |
|-----------|-------|
| Size | 356 bytes |
| Format | Plain text |
| Purpose | Lists files that exceed Git's recommended size limit |
| In .gitignore | Yes — not tracked |

Contains paths to binary files (`.bin`, `.xlsx`, large `.txt` dumps) that should not be committed to Git or should use Git LFS.

---

### `push_log.txt` — Git Push Operation Log

| Attribute | Value |
|-----------|-------|
| Size | 2,194 bytes |
| Format | Plain text (Git CLI output) |
| Purpose | Captured output from `git push` operations |
| In .gitignore | Yes — not tracked |

Records the results of pushing the reorganized repository to the remote GitHub origin (`https://github.com/Queen-s-High-Performance-Computing/2025-2026_teams_files.git`).

---

### `.git/` — Git Repository Metadata

| Attribute | Value |
|-----------|-------|
| Type | Directory |
| Purpose | Git version control metadata |
| Contents | Object database, refs, HEAD, config |
| Remote | `https://github.com/Queen-s-High-Performance-Computing/2025-2026_teams_files.git` |

---

### `.venv/` — Python Virtual Environment

| Attribute | Value |
|-----------|-------|
| Type | Directory |
| Purpose | Isolated Python environment for analysis scripts |
| In .gitignore | Yes — not tracked |
| Contents | Python interpreter, pip, installed packages (matplotlib, numpy, flask, etc.) |

---

### `johnnie-comm-phase/` — Active Development Branch

| Attribute | Value |
|-----------|-------|
| Type | Directory |
| Purpose | Active development working copy of the communication phase branch |
| Note | This is the **live working directory** — separate from the archived copy at `07_archive/johnnie_comm_phase/` |
| Contents | Mirrors `07_archive/johnnie_comm_phase/` with potentially newer modifications |
| Status | Active — may contain uncommitted changes |

This directory contains the same file structure as the archived `johnnie_comm_phase` branch (38 files, 7 subdirectories). See [07_archive_branches.md](07_archive_branches.md) for the full file manifest.
