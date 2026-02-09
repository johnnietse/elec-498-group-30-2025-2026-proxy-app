#!/bin/bash

# ================= CONFIGURATION =================
MPI_RANKS=${1:-8}
PYTHON_SCRIPT="test.py"
INPUT_FILE="in.lj.miniMD"
# Verify your RAPL path, this is standard for Intel
RAPL_FILE="/sys/class/powercap/intel-rapl:0/energy_uj"
MAX_RAPL_FILE="/sys/class/powercap/intel-rapl:0/max_energy_range_uj"

echo "=========================================================="
echo "   CAPSTONE ENERGY TEST: ISOLATED CORES"
echo "=========================================================="

# Trap: Ensures python dies if you Ctrl+C the bash script
trap "pkill -f $PYTHON_SCRIPT; exit" INT TERM EXIT

# ================= CORE ALLOCATOR =================
# Allocates first N cores to Workers, last core to Monitor
get_core_allocation() {
    local needed_ranks=$1
    taskset -cp $$ | awk -F': ' '{print $2}' | python3 -c "
import sys
def parse_ranges(r):
    cores = []
    if not r: return []
    for part in r.split(','):
        if '-' in part:
            s, e = map(int, part.split('-'))
            cores.extend(range(s, e + 1))
        else:
            cores.append(int(part))
    return sorted(list(set(cores)))

try:
    input_str = sys.stdin.read().strip()
    all_cores = parse_ranges(input_str)
    needed = int($needed_ranks)

    # Check we have enough cores (Rank + 1 Monitor)
    if len(all_cores) < (needed + 1):
        print(f'ERROR: Need {needed+1} cores, but only have {len(all_cores)}', file=sys.stderr)
        sys.exit(1)

    mon_core = all_cores.pop()
    worker_cores = all_cores[:needed]

    # === FIX: Use double quotes on the outside ===
    print(f\"{','.join(map(str, worker_cores))}|{mon_core}\")

except Exception as e:
    print(f'ERROR: {e}', file=sys.stderr)
    sys.exit(1)
"
}

# ================= ENERGY HELPERS =================
start_energy_monitor() {
    cat "$RAPL_FILE" > start_snapshot.tmp 2>/dev/null || echo "0" > start_snapshot.tmp
}

stop_energy_monitor() {
    local END_VAL=$(cat "$RAPL_FILE" 2>/dev/null || echo 0)
    local START_VAL=$(cat start_snapshot.tmp 2>/dev/null || echo 0)
    local MAX_VAL=$(cat "$MAX_RAPL_FILE" 2>/dev/null || echo 262143328850)
    # Handle overflow if counter reset
    python3 -c "print($END_VAL - $START_VAL if ($END_VAL - $START_VAL) >= 0 else ($END_VAL - $START_VAL) + $MAX_VAL)"
    rm -f start_snapshot.tmp
}

# ================= BENCHMARK LOOP =================
run_benchmark() {
    local mode=$1

    # 1. Calculate Isolation
    local ALLOC_STR=$(get_core_allocation $MPI_RANKS)

    # If python failed, stop immediately
    if [ $? -ne 0 ] || [[ $ALLOC_STR == "ERROR"* ]]; then
        echo "Core allocation failed: $ALLOC_STR" >&2
        exit 1
    fi

    local WORKER_CORES=$(echo "$ALLOC_STR" | cut -d'|' -f1)
    local MONITOR_CORE=$(echo "$ALLOC_STR" | cut -d'|' -f2)

    if [ "$mode" == "MONITORED" ]; then
        echo "   [ISOLATION] Workers: $WORKER_CORES | Monitor: $MONITOR_CORE" >&2
    fi

    start_energy_monitor
    local start_t=$(date +%s.%N)

    if [ "$mode" == "BASELINE" ]; then
        # Run standard, bound to worker cores only
        taskset -c $WORKER_CORES mpirun -np $MPI_RANKS --bind-to core ./miniMD_openmpi -i $INPUT_FILE > run_baseline.log 2>&1

    elif [ "$mode" == "MONITORED" ]; then
        # 1. Start Monitor on its EXCLUSIVE core
        #    -u: Unbuffered output (logs immediately)
        #    --heartbeat: Prints utilization status every 0.5s
        taskset -c $MONITOR_CORE python3 -u $PYTHON_SCRIPT --heartbeat --cores "$WORKER_CORES" > monitor_output.log 2>&1 &
        MON_PID=$!

        # 2. Wait 4 Seconds as requested (Monitor warms up)
        sleep 4

        # 3. Check if monitor crashed
        if ! kill -0 $MON_PID 2>/dev/null; then
            echo "ERROR: Monitor died early! Check monitor_output.log" >&2
        fi

        # 4. Run App on WORKER cores only
        taskset -c $WORKER_CORES mpirun -np $MPI_RANKS --bind-to core ./miniMD_openmpi -i $INPUT_FILE > run_monitored.log 2>&1

        # 5. Stop Monitor Instantly
        kill -SIGINT $MON_PID 2>/dev/null
        wait $MON_PID 2>/dev/null
    fi

    local energy_raw=$(stop_energy_monitor)
    local end_t=$(date +%s.%N)

    local energy_joules=$(echo "$energy_raw / 1000000" | bc -l)
    local time_diff=$(echo "$end_t - $start_t" | bc -l)

    echo "$time_diff $energy_joules"
}

# ================= RUN =================

echo "1. Running Baseline..."
read base_time base_energy <<< $(run_benchmark "BASELINE")
echo "   Baseline:  ${base_time}s | ${base_energy}J"

echo "2. Running Monitored..."
read mon_time mon_energy <<< $(run_benchmark "MONITORED")
echo "   Monitored: ${mon_time}s | ${mon_energy}J"

# ================= RESULTS =================
echo ""
echo "================ RESULTS ================"
# Avoid division by zero if baseline failed
if (( $(echo "$base_time > 0" | bc -l) )); then
    time_pct=$(echo "(($mon_time - $base_time) / $base_time) * 100" | bc -l)
    saved_j=$(echo "$base_energy - $mon_energy" | bc -l)

    printf "Runtime Impact: %+.2f%%\n" $time_pct
    printf "Energy Savings: %s Joules\n" $saved_j
else
    echo "Error: Baseline time was 0 (Did the run fail?)"
fi