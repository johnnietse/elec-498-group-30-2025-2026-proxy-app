#!/bin/bash

# ================= CONFIGURATION =================
MPI_RANKS=${1:-8}  # Default to 8 ranks if not provided
PYTHON_SCRIPT="test.py"
INPUT_FILE="in.lj.miniMD"
RAPL_FILE="/sys/class/powercap/intel-rapl:0/energy_uj"
MAX_RAPL_FILE="/sys/class/powercap/intel-rapl:0/max_energy_range_uj"

echo "=========================================================="
echo "   CAPSTONE ENERGY TEST: ADAPTIVE CORE BINDING"
echo "   Ranks: $MPI_RANKS | Input: $INPUT_FILE"
echo "=========================================================="

trap "pkill -f $PYTHON_SCRIPT; exit" INT TERM EXIT

# ================= HELPER FUNCTIONS =================

# ADAPTIVE CORE ALLOCATOR
# Reads the job's assigned cores and splits them:
# - Last core -> Monitor
# - First N cores -> Workers
# Output format: "WORKER_LIST|MONITOR_CORE"
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
    return sorted(list(set(cores))) # Sort and remove duplicates

try:
    # 1. Get List of ALL cores assigned to this job
    input_str = sys.stdin.read().strip()
    all_cores = parse_ranges(input_str)
    
    needed = int($needed_ranks)
    
    # 2. Safety Checks
    if len(all_cores) < (needed + 1):
        # We need N workers + 1 Monitor
        print(f'ERROR: Not enough cores! Have {len(all_cores)}, need {needed}+1', file=sys.stderr)
        sys.exit(1)

    # 3. Allocation Strategy
    # Monitor gets the LAST core (usually furthest from Rank 0)
    mon_core = all_cores.pop() 
    
    # Workers get the FIRST 'needed' cores
    worker_cores = all_cores[:needed]
    
    # 4. Format Output
    w_str = ','.join(map(str, worker_cores))
    print(f'{w_str}|{mon_core}')

except Exception as e:
    print(f'ERROR: {e}', file=sys.stderr)
    sys.exit(1)
"
}

set_max_freq() {
    local CORES=$1
    IFS=',' read -ra C_LIST <<< "$CORES"
    for core in "${C_LIST[@]}"; do
        local f="/sys/devices/system/cpu/cpu$core/cpufreq/scaling_setspeed"
        if [ -w "$f" ]; then
            echo 2000000 > "$f" 2>/dev/null
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

    python3 -c "
s = int('$START_VAL')
e = int('$END_VAL')
m = int('$MAX_VAL')
diff = e - s
if diff < 0: diff += m
print(diff)
"
    rm -f start_snapshot.tmp
}

# ================= RUN LOGIC =================

run_benchmark() {
    local mode=$1
    
    # 1. ADAPTIVE ALLOCATION
    # This calls the Python logic to get the exact core lists
    local ALLOC_STR=$(get_core_allocation $MPI_RANKS)
    
    # Check for errors from Python
    if [[ $ALLOC_STR == "ERROR"* ]]; then
        echo "$ALLOC_STR" >&2
        exit 1
    fi

    local WORKER_CORES=$(echo "$ALLOC_STR" | cut -d'|' -f1)
    local MONITOR_CORE=$(echo "$ALLOC_STR" | cut -d'|' -f2)

    # 2. Reset Frequency (Best Effort)
    set_max_freq "$WORKER_CORES,$MONITOR_CORE"

    start_energy_monitor
    local start_t=$(date +%s.%N)
    
    if [ "$mode" == "BASELINE" ]; then
        # IMPORTANT: taskset here RESTRICTS mpirun to only the 8 cores we chose.
        # mpirun will see 8 slots and bind Rank 0->1st core, Rank 1->2nd core, etc.
        taskset -c $WORKER_CORES mpirun -np $MPI_RANKS --bind-to core ./miniMD_openmpi -i $INPUT_FILE > run_baseline.log 2>&1
        
    elif [ "$mode" == "MONITORED" ]; then
        # Pass ONLY the worker list to Python so it doesn't monitor unused cores
        taskset -c $MONITOR_CORE python3 $PYTHON_SCRIPT --cores "$WORKER_CORES" > monitor_output.log 2>&1 &
        MON_PID=$!
        
        sleep 2
        
        if ! kill -0 $MON_PID 2>/dev/null; then
            echo "ERROR: Monitor died unexpectedly!" >&2
        fi

        taskset -c $WORKER_CORES mpirun -np $MPI_RANKS --bind-to core ./miniMD_openmpi -i $INPUT_FILE > run_monitored.log 2>&1
        
        kill -SIGINT $MON_PID 2>/dev/null
        wait $MON_PID 2>/dev/null
    fi
    
    local energy_raw=$(stop_energy_monitor)
    local end_t=$(date +%s.%N)

    local energy_joules=$(echo "$energy_raw / 1000000" | bc -l)
    local time_diff=$(echo "$end_t - $start_t" | bc -l)
    
    echo "$time_diff $energy_joules"
}

# ================= MAIN EXECUTION =================

if [ ! -r "$RAPL_FILE" ]; then
    echo "WARNING: Cannot read RAPL energy file. Energy results will be 0."
fi

echo "1. Running Baseline..."
read base_time base_energy <<< $(run_benchmark "BASELINE")
echo "   Baseline:  ${base_time}s | ${base_energy}J"

echo "2. Running Monitored..."
read mon_time mon_energy <<< $(run_benchmark "MONITORED")
echo "   Monitored: ${mon_time}s | ${mon_energy}J"

# ================= REPORT =================
echo ""
echo "================ RESULTS ================"
time_pct=$(echo "(($mon_time - $base_time) / $base_time) * 100" | bc -l)
printf "Runtime Impact: %+.2f%%\n" $time_pct

saved_j=$(echo "$base_energy - $mon_energy" | bc -l)
printf "Energy Savings: %s Joules\n" $saved_j

python3 -c "
saved = float('$saved_j')
if saved > 0: print('STATUS: SUCCESS! Energy Saved.')
else: print('STATUS: No Savings.')
"
echo "========================================="