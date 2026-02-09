#!/bin/bash

# ================= CONFIGURATION =================
MPI_RANKS=${1:-8}
PYTHON_SCRIPT="test.py"
INPUT_FILE="in.lj.miniMD"
RAPL_FILE="/sys/class/powercap/intel-rapl:0/energy_uj"
MAX_RAPL_FILE="/sys/class/powercap/intel-rapl:0/max_energy_range_uj"

# Frequency to reset to (in kHz)
RESET_FREQ="2000000" 
TOTAL_CORES=32

echo "=========================================================="
echo "   CAPSTONE ENERGY TEST: ISOLATED CORES"
echo "=========================================================="

trap "pkill -f $PYTHON_SCRIPT; exit" INT TERM EXIT

# ================= CORE ALLOCATOR =================
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
    if len(all_cores) < (needed + 1):
        sys.exit(1)
    mon_core = all_cores.pop()
    worker_cores = all_cores[:needed]
    print(f\"{','.join(map(str, worker_cores))}|{mon_core}\")
except:
    sys.exit(1)
"
}

# ================= UTILS =================
reset_all_cores() {
    # Silence output to keep logs clean
    # echo "   [RESET] Forcing ALL ${TOTAL_CORES} cores to ${RESET_FREQ}kHz..." >&2
    for (( core=0; core<TOTAL_CORES; core++ )); do
        local gov_file="/sys/devices/system/cpu/cpu$core/cpufreq/scaling_governor"
        local speed_file="/sys/devices/system/cpu/cpu$core/cpufreq/scaling_setspeed"
        if [ -w "$gov_file" ]; then
            echo "userspace" > "$gov_file" 2>/dev/null
            echo "$RESET_FREQ" > "$speed_file" 2>/dev/null
        fi
    done
}

start_energy_monitor() {
    cat "$RAPL_FILE" > start_snapshot.tmp 2>/dev/null || echo "0" > start_snapshot.tmp
}

stop_energy_monitor() {
    local END_VAL=$(cat "$RAPL_FILE" 2>/dev/null || echo 0)
    local START_VAL=$(cat start_snapshot.tmp 2>/dev/null || echo 0)
    local MAX_VAL=$(cat "$MAX_RAPL_FILE" 2>/dev/null || echo 262143328850)
    python3 -c "print($END_VAL - $START_VAL if ($END_VAL - $START_VAL) >= 0 else ($END_VAL - $START_VAL) + $MAX_VAL)"
    rm -f start_snapshot.tmp
}

# ================= BENCHMARK LOOP =================
run_benchmark() {
    local mode=$1
    
    # 0. Clean Frequency Slate
    reset_all_cores

    # 1. Get Isolation Info
    local ALLOC_STR=$(get_core_allocation $MPI_RANKS)
    if [ $? -ne 0 ]; then exit 1; fi
    local WORKER_CORES=$(echo "$ALLOC_STR" | cut -d'|' -f1)
    local MONITOR_CORE=$(echo "$ALLOC_STR" | cut -d'|' -f2)

    # ================= BASELINE LOGIC =================
    if [ "$mode" == "BASELINE" ]; then
        start_energy_monitor
        local start_t=$(date +%s.%N)

        # taskset -c $WORKER_CORES mpirun -np $MPI_RANKS --bind-to core ./miniMD_openmpi -i $INPUT_FILE > run_baseline.log 2>&1
        mpirun -np $MPI_RANKS \
            --cpu-set $WORKER_CORES \
            --bind-to core \
            --report-bindings \
            ./miniMD_openmpi -i $INPUT_FILE > run_baseline.log 2>&1

        local energy_raw=$(stop_energy_monitor)
        local end_t=$(date +%s.%N)

    # ================= MONITORED LOGIC =================
    elif [ "$mode" == "MONITORED" ]; then
        # 1. Start Monitor on the MONITOR_CORE (e.g., Core 31)
        #    This is completely safe because MPI is using 0-23.
        taskset -c $MONITOR_CORE python3 -u $PYTHON_SCRIPT --heartbeat --cores "$WORKER_CORES" > monitor_output.log 2>&1 &
        MON_PID=$!

        # 2. Warmup (Sleep 4s)
        sleep 4

        # 3. Start Timer
        start_energy_monitor
        local start_t=$(date +%s.%N)

        # 4. Run MPI on WORKER_CORES (e.g., 0-23)
        #    Using --cpu-set ensures it NEVER touches Core 31.
       mpirun -np $MPI_RANKS \
            --cpu-set $WORKER_CORES \
            --bind-to core \
            --report-bindings \
            ./miniMD_openmpi -i $INPUT_FILE > run_monitored.log 2>&1

        # 5. Stop Timer
        local end_t=$(date +%s.%N)
        local energy_raw=$(stop_energy_monitor)

        # 6. Kill Monitor
        kill -SIGINT $MON_PID 2>/dev/null
        wait $MON_PID 2>/dev/null
    fi

    # ================= CALCULATION =================
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
if (( $(echo "$base_time > 0" | bc -l) )); then
    time_pct=$(echo "(($mon_time - $base_time) / $base_time) * 100" | bc -l)
    saved_j=$(echo "$base_energy - $mon_energy" | bc -l)
    # New Metric: Energy % Saved
    energy_pct=$(echo "(($base_energy - $mon_energy) / $base_energy) * 100" | bc -l)

    printf "Runtime Impact: %+.2f%%\n" $time_pct
    printf "Energy Savings: %s Joules (%.2f%%)\n" $saved_j $energy_pct
else
    echo "Error: Baseline time was 0"
fi