# 08_test_gui/ — Test GUI Directory

**Parent:** Repository Root  
**Purpose:** Contains experimental user-facing dashboards designed to monitor the system's performance in real-time.  
**Usage:** This tool is optional and primarily built to satisfy the Capstone Blueprint's Optional Interface requirements. Relies on `curses` and standard terminal rendering. Should run in a separate SSH/Tmux session alongside the main experiment.

---

## Directory Structure

```
08_test_gui/
└── README.md    (720 bytes · 11 lines)
```

**Status:** Currently contains only the README. The actual dashboard tools were copied to `02_src/monitoring/` and remain in `07_archive/johnnie_comm_phase/`.

---

## File Documentation

### `README.md`
| Attribute | Value |
|-----------|-------|
| Size | 720 bytes (11 lines) |
| Content | Describes the TUI Dashboard, its curses-based rendering, and its role as an optional Blueprint requirement |

---

## Intended Contents (from `reorganize_workspace.ps1` Phase 6)

These files were configured for copy into `08_test_gui/` but the sources may not have been available at runtime:

### `test_gui.py` — Curses TUI Dashboard
| Attribute | Value |
|-----------|-------|
| Size | 10,177 bytes |
| Language | Python 3 |
| Framework | `curses` |
| Location | `07_archive/johnnie_comm_phase/test_gui.py` |
| Purpose | Terminal User Interface showing real-time per-core frequencies, governor states, and phase information |
| Input | Reads `/sys/devices/system/cpu/cpuN/cpufreq/` and optionally shared-memory phase hints |
| Key Features | Color-coded frequency bars, governor indicators, sparkline history |

### `test_gui_web.py` — Web-Based Dashboard
| Attribute | Value |
|-----------|-------|
| Size | 16,651 bytes |
| Language | Python 3 |
| Framework | Flask / HTTP |
| Location | `07_archive/johnnie_comm_phase/test_gui_web.py` |
| Purpose | Browser-accessible dashboard for remote monitoring |
| Endpoint | HTTP server serving real-time metrics as HTML/JSON |
| Advantage | Accessible from any browser without terminal requirements |
| Limitation | Higher latency than TUI, requires Flask dependency |

### `test_gui_windowed.py` — Tkinter Windowed Dashboard
| Attribute | Value |
|-----------|-------|
| Size | 7,734 bytes |
| Language | Python 3 |
| Framework | `tkinter` |
| Location | `07_archive/johnnie_comm_phase/test_gui_windowed.py` |
| Purpose | Native windowed GUI for desktop monitoring |
| Advantage | Familiar GUI interface with window management |
| Limitation | Requires X11 forwarding on HPC cluster (high latency) |

### `verify_file_sizes.py` — Checkpoint Verification Utility
| Attribute | Value |
|-----------|-------|
| Size | 6,933 bytes |
| Language | Python 3 |
| Location | `07_archive/johnnie_comm_phase/verify_file_sizes.py` |
| Purpose | Verifies that checkpoint file sizes match expected per-rank data calculations |
| Input | Checkpoint directory path |
| Output | Comparison of actual vs expected sizes with pass/fail indicator |

---

## Dashboard Comparison Matrix

| Feature | `test_gui.py` (TUI) | `test_gui_web.py` (Web) | `test_gui_windowed.py` (Tkinter) | `dashboard.py` (Production) |
|---------|---------------------|------------------------|----------------------------------|----------------------------|
| Framework | curses | Flask | tkinter | curses |
| Location | Archive | Archive | Archive | `02_src/monitoring/` |
| Remote Access | SSH terminal | Browser | X11 forwarding | SSH terminal |
| Latency | <100ms | ~500ms | ~200ms | <500ms |
| Dependencies | stdlib only | Flask | tkinter | stdlib only |
| Phase Hints | Optional | Optional | Optional | Full support |
| Production Use | No | No | No | **Yes** |
| Author | Johnnie | Johnnie | Johnnie | Zane |

---

## Notes

- The production dashboard (`dashboard.py` in `02_src/monitoring/`) superseded all three experimental dashboards
- The TUI approach was chosen for production because it has zero dependencies, works over SSH without X11, and provides sub-second refresh
- Web and windowed variants were exploratory prototypes that proved the visualization concept before the final TUI was developed
