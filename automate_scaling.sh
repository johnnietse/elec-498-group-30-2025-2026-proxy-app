#!/bin/bash
NUM_CORES=$1
CORE_RANGE=$2

export OMP_NUM_THREADS=1
export OMP_PROC_BIND=true
export OMP_PLACES=cores

NUM_RUNS=5                    
IDLE_MEASURE_TIME=10          # Seconds to measure background leakage

ENERGY_FILE="/sys/class/powercap/intel-rapl:0:0/energy_uj"
MAX_RANGE=$(cat /sys/class/powercap/intel-rapl:0:0/max_energy_range_uj)
CSV_FILE="${NUM_CORES}_core_scaling_results.csv"
LOG_FILE="log_${NUM_CORES}_cores.out"

# Initialize CSV with a header
echo "Run,Time_Sec_${NUM_CORES},Total_J_${NUM_CORES},Dynamic_J_${NUM_CORES}, Avg_Power_W__${NUM_CORES}" > "$CSV_FILE"

ample_energy() {
    local RUN_ID=$1
    local ACCUMULATED_UJ=0
    local PREV=$(cat "$ENERGY_FILE")
    
    while [ -f ".running_$RUN_ID" ]; do
        CURRENT=$(cat "$ENERGY_FILE")
        DIFF=$(echo "$CURRENT - $PREV" | bc)
        
        # Handle wrap-around
        if [ "$(echo "$DIFF < 0" | bc)" -eq 1 ]; then
            DIFF=$(echo "$DIFF + $MAX_RANGE" | bc)
        fi
        
        ACCUMULATED_UJ=$(echo "$ACCUMULATED_UJ + $DIFF" | bc)
        PREV=$CURRENT
        echo "$ACCUMULATED_UJ" > ".energy_tmp_$RUN_ID"
        sleep 10
    done
}

# Measure Idle Baseline
# Isolates the 'leakage power' of the socket before work starts
echo "Measuring ${IDLE_MEASURE_TIME}s idle baseline for $NUM_CORES core test..."
I_BEFORE=$(cat "$ENERGY_FILE")
sleep $IDLE_MEASURE_TIME
I_AFTER=$(cat "$ENERGY_FILE")
IDLE_DIFF=$(echo "$I_AFTER - $I_BEFORE" | bc)
if [ "$(echo "$IDLE_DIFF < 0" | bc)" -eq 1 ]; then IDLE_DIFF=$(echo "$IDLE_DIFF + $MAX_RANGE" | bc); fi
IDLE_PWR=$(echo "scale=6; ($IDLE_DIFF / 1000000) / $IDLE_MEASURE_TIME" | bc)

# 2. Execution Loop
for (( i=1; i<=$NUM_RUNS; i++ ))
do
    echo "Starting Run $i of $NUM_RUNS..."
    
    RUN_ID="${NUM_CORES}_${i}"
    touch ".running_$RUN_ID"
    
    # Start background monitor to catch counter resets during long runs
    sample_energy "$RUN_ID" &
    MONITOR_PID=$!

    START_NS=$(date +%s%N)
    
    # Run miniMD with strict pinning
    numactl --physcpubind="$CORE_RANGE" --localalloc \
    mpirun -np "$NUM_CORES" --map-by core --bind-to core \
    ./miniMD_openmpi -i in.lj.miniMD >> "$LOG_FILE" 2>&1
    
    END_NS=$(date +%s%N)
    # Stop monitor safely
    rm ".running_$RUN_ID"
    wait $MONITOR_PID

    TOTAL_UJ=$(cat ".energy_tmp_$RUN_ID")
    rm ".energy_tmp_$RUN_ID"
    
    RUNTIME=$(echo "scale=9; ($END_NS - $START_NS) / 1000000000" | bc)
    TOTAL_J=$(echo "scale=6; $TOTAL_UJ / 1000000" | bc)
    
    # Calculation: Dynamic Energy = Total - (Idle Leakage * Time)
    DYNAMIC_J=$(echo "scale=6; $TOTAL_J - ($IDLE_PWR * $RUNTIME)" | bc)
    POWER_W=$(echo "scale=2; $TOTAL_J / $RUNTIME" | bc)
    
    # Save results
    echo "$i,$RUNTIME,$TOTAL_J,$DYNAMIC_J, $POWER_W" >> "$CSV_FILE"
done

echo "Finished $NUM_RUNS runs for $NUM_CORES cores."
