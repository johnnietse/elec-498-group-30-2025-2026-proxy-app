#!/usr/bin/env python3
import os
import time
import mmap
import ctypes
import argparse
import curses
from collections import Counter, deque

PHASE_COMPUTE      = 0
PHASE_COMMUNICATE  = 1
PHASE_EXCHANGE     = 2
PHASE_BORDERS      = 3
PHASE_REVERSE      = 4
PHASE_IO           = 5
PHASE_COMMUNICATION_ACTIVE = 6
PHASE_COMMUNICATION_PASSIVE   = 7
PHASE_DONE         = 8

PHASE_NAMES = {
    0: "COMPUTE",
    1: "COMMUNICATE",
    2: "EXCHANGE",
    3: "BORDERS",
    4: "REVERSE",
    5: "IO",
    6: "COMMUNICATION_ACTIVE",
    7: "COMMUNICATION_PASSIVE",
    8: "DONE",
}

PHASE_MAGIC = 0x50485331
MAX_PHASE_SLOTS = 64
RESERVED_CORE = 31
MONITOR_CORE = 30
MAX_MHZ = 3600.0
SPARKS = "▁▂▃▄▅▆▇█"

class PhaseSlot(ctypes.Structure):
    _fields_ = [
        ("seq", ctypes.c_uint32),
        ("rank", ctypes.c_int32),
        ("core", ctypes.c_int32),
        ("phase", ctypes.c_uint32),
        ("t_ns", ctypes.c_uint64),
    ]

class PhaseTable(ctypes.Structure):
    _fields_ = [
        ("magic", ctypes.c_uint32),
        ("nslots", ctypes.c_uint32),
        ("slots", PhaseSlot * MAX_PHASE_SLOTS),
    ]


def read_text(path):
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except Exception:
        return None


def read_freqs(num_cores):
    freqs = []
    govs = []
    for core in range(num_cores):
        fpath = f"/sys/devices/system/cpu/cpu{core}/cpufreq/scaling_cur_freq"
        gpath = f"/sys/devices/system/cpu/cpu{core}/cpufreq/scaling_governor"
        raw = read_text(fpath)
        gov = read_text(gpath) or "?"
        if raw is None:
            freqs.append(None)
        else:
            try:
                freqs.append(int(raw) / 1000.0)
            except ValueError:
                freqs.append(None)
        govs.append(gov)
    return freqs, govs


def open_phase_map(path):
    if not os.path.exists(path):
        return None, None
    try:
        size = ctypes.sizeof(PhaseTable)
        f = open(path, "rb")
        mm = mmap.mmap(f.fileno(), size, access=mmap.ACCESS_READ)
        return f, mm
    except Exception:
        return None, None


def read_phase_table(mm):
    if mm is None:
        return []
    try:
        table = PhaseTable.from_buffer_copy(mm[:ctypes.sizeof(PhaseTable)])
        if table.magic != PHASE_MAGIC or table.nslots <= 0:
            return []
        out = []
        for i in range(min(table.nslots, MAX_PHASE_SLOTS)):
            s = table.slots[i]
            if s.core >= 0:
                out.append((s.rank, s.core, s.phase, s.t_ns))
        return out
    except Exception:
        return []


def mhz_color(mhz):
    if mhz is None:
        return 5
    if mhz < 1400:
        return 2
    if mhz < 2200:
        return 3
    return 4


def governor_short(g):
    if g == "performance":
        return "P"
    if g == "userspace":
        return "U"
    return g[:1].upper() if g else "?"


def bar(value, width, max_value=MAX_MHZ):
    if value is None:
        return " " * width
    filled = max(0, min(width, int((value / max_value) * width)))
    return "█" * filled + "░" * (width - filled)


def sparkline(values, width):
    vals = list(values)[-width:]
    if not vals:
        return ""
    low = min(vals)
    high = max(vals)
    if high - low < 1e-6:
        return SPARKS[len(SPARKS) // 2] * len(vals)
    out = []
    for v in vals:
        idx = int((v - low) / (high - low) * (len(SPARKS) - 1))
        out.append(SPARKS[idx])
    return "".join(out)


def draw_box(stdscr, y, x, h, w, title):
    try:
        stdscr.attron(curses.color_pair(1))
        stdscr.addstr(y, x, "┌" + "─" * (w - 2) + "┐")
        for row in range(1, h - 1):
            stdscr.addstr(y + row, x, "│")
            stdscr.addstr(y + row, x + w - 1, "│")
        stdscr.addstr(y + h - 1, x, "└" + "─" * (w - 2) + "┘")
        label = f" {title} "
        if len(label) < w - 2:
            stdscr.addstr(y, x + 2, label, curses.color_pair(6) | curses.A_BOLD)
        stdscr.attroff(curses.color_pair(1))
    except curses.error:
        pass


def write(stdscr, y, x, text, color=0, attr=0):
    try:
        stdscr.addstr(y, x, text, curses.color_pair(color) | attr)
    except curses.error:
        pass


def phase_summary(phase_rows):
    c = Counter(PHASE_NAMES.get(p, str(p)) for _, _, p, _ in phase_rows)
    order = [
        "COMPUTE", "COMMUNICATE", "EXCHANGE", "BORDERS",
        "REVERSE", "IO", "COMMUNICATION_ACTIVE", "COMMUNICATION_PASSIVE", "DONE"
    ]
    return [(name, c[name]) for name in order if c[name] > 0]


def main_loop(stdscr, args):
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_CYAN, -1)
    curses.init_pair(2, curses.COLOR_RED, -1)
    curses.init_pair(3, curses.COLOR_YELLOW, -1)
    curses.init_pair(4, curses.COLOR_GREEN, -1)
    curses.init_pair(5, curses.COLOR_WHITE, -1)
    curses.init_pair(6, curses.COLOR_MAGENTA, -1)

    history = deque(maxlen=120)
    phase_file = None
    phase_map = None
    last_reopen = 0.0

    while True:
        now = time.time()
        if phase_map is None and now - last_reopen > 1.0:
            phase_file, phase_map = open_phase_map(args.hint_file)
            last_reopen = now

        freqs, govs = read_freqs(args.cores)
        valid = [f for f in freqs if f is not None]
        avg_mhz = sum(valid) / len(valid) if valid else 0.0
        min_mhz = min(valid) if valid else 0.0
        max_mhz = max(valid) if valid else 0.0
        throttled = sum(1 for f in valid if f < args.low_mark)
        perf_count = sum(1 for g in govs if g == "performance")
        user_count = sum(1 for g in govs if g == "userspace")
        history.append(avg_mhz)

        try:
            phase_rows = read_phase_table(phase_map)
        except ValueError:
            phase_rows = []
            phase_file, phase_map = None, None

        stdscr.erase()
        H, W = stdscr.getmaxyx()

        title = " miniMD PHASE-AWARE DVFS LIVE DASHBOARD "
        subtitle = "q: quit   r: refresh phase map   monitor: per-core freq + governor + app phase"
        write(stdscr, 0, max(0, (W - len(title)) // 2), title, 6, curses.A_BOLD)
        write(stdscr, 1, max(0, (W - len(subtitle)) // 2), subtitle, 1)

        # KPI row
        box_w = max(18, W // 5 - 1)
        kpis = [
            ("AVG MHz", f"{avg_mhz:6.0f}"),
            ("MIN / MAX", f"{min_mhz:4.0f} / {max_mhz:4.0f}"),
            ("LOW FREQ CORES", f"{throttled:2d}"),
            ("PERF / USER", f"{perf_count:2d} / {user_count:2d}"),
            ("PHASE SLOTS", f"{len(phase_rows):2d}"),
        ]
        y0 = 3
        for i, (k, v) in enumerate(kpis):
            x0 = i * box_w
            if x0 + box_w >= W:
                break
            draw_box(stdscr, y0, x0, 5, box_w, k)
            write(stdscr, y0 + 2, x0 + 2, v, 4, curses.A_BOLD)

        # History panel
        hist_y = 9
        hist_h = 5
        draw_box(stdscr, hist_y, 0, hist_h, W, "Average Frequency Trend")
        hist = sparkline(history, max(10, W - 22))
        write(stdscr, hist_y + 2, 2, hist, 1)
        write(stdscr, hist_y + 2, min(W - 18, len(hist) + 4), f"{avg_mhz:6.0f} MHz", 4, curses.A_BOLD)

        # Left: core grid
        grid_y = 15
        left_w = max(50, int(W * 0.62))
        right_x = left_w + 1
        right_w = W - right_x
        grid_h = H - grid_y - 1
        draw_box(stdscr, grid_y, 0, max(8, grid_h), left_w, "Per-Core Frequency")

        cols = 2 if left_w < 90 else 3
        rows_per_col = (args.cores + cols - 1) // cols
        inner_w = left_w - 4
        col_w = max(24, inner_w // cols)
        bar_w = max(8, col_w - 17)

        for idx in range(args.cores):
            c = idx // rows_per_col
            r = idx % rows_per_col
            y = grid_y + 2 + r
            x = 2 + c * col_w
            if y >= H - 1 or x + col_w >= left_w:
                continue
            mhz = freqs[idx]
            gov = govs[idx]
            color = mhz_color(mhz)
            if mhz is None:
                line = f"cpu{idx:02d} N/A"
                write(stdscr, y, x, line, 5)
            else:
                line = f"cpu{idx:02d} {mhz:4.0f} {governor_short(gov)} "
                write(stdscr, y, x, line, color)
                write(stdscr, y, x + len(line), bar(mhz, bar_w), color)

        # Right: phases and legend
        draw_box(stdscr, grid_y, right_x, max(8, grid_h), right_w, "Application Phases")
        py = grid_y + 2
        if not phase_rows:
            write(stdscr, py, right_x + 2, f"Waiting for {args.hint_file}", 3)
        else:
            summary = phase_summary(phase_rows)
            write(stdscr, py, right_x + 2, "Phase totals:", 6, curses.A_BOLD)
            py += 1
            for name, count in summary[:min(8, grid_h - 8)]:
                write(stdscr, py, right_x + 2, f"{name:<14} {count:2d}", 4 if name in ("COMPUTE", "COMMUNICATION_ACTIVE") else 3)
                py += 1
            py += 1
            write(stdscr, py, right_x + 2, "Rank -> core mapping:", 6, curses.A_BOLD)
            py += 1
            phase_rows_sorted = sorted(phase_rows, key=lambda x: x[0])
            for rank, core, phase, _ in phase_rows_sorted[:max(0, H - py - 2)]:
                pname = PHASE_NAMES.get(phase, str(phase))
                col = 4 if pname in ("COMPUTE", "COMMUNICATION_ACTIVE") else 2 if pname in ("IO", "COMMUNICATION_PASSIVE") else 3
                write(stdscr, py, right_x + 2, f"rank {rank:02d} -> cpu{core:02d}  {pname}", col)
                py += 1

        footer = f"refresh {args.refresh:.2f}s | low-mark {args.low_mark:.0f} MHz | reserved cpu{RESERVED_CORE}, monitor cpu{MONITOR_CORE}"
        write(stdscr, H - 1, 1, footer[:max(0, W - 2)], 1)

        stdscr.refresh()
        stdscr.timeout(int(args.refresh * 1000))
        ch = stdscr.getch()
        if ch in (ord('q'), ord('Q')):
            break
        if ch in (ord('r'), ord('R')):
            try:
                if phase_map is not None:
                    phase_map.close()
                if phase_file is not None:
                    phase_file.close()
            except Exception:
                pass
            phase_file, phase_map = None, None


def main():
    ap = argparse.ArgumentParser(description="Live terminal dashboard for miniMD DVFS demos")
    ap.add_argument("--cores", type=int, default=32, help="Number of CPU cores to display")
    ap.add_argument("--refresh", type=float, default=0.5, help="Refresh period in seconds")
    ap.add_argument("--low-mark", type=float, default=1600.0, help="Count frequencies below this as throttled")
    ap.add_argument("--hint-file", default=os.environ.get("PHASE_HINT_PATH", "/dev/shm/minimd_phase_hints.bin"), help="Shared-memory phase hint file")
    args = ap.parse_args()
    curses.wrapper(main_loop, args)


if __name__ == "__main__":
    main()