#!/bin/bash

# Configuration
CSV_FILE="8_cores_simulation_results_${SLURM_JOB_ID:-manual}.csv"
ENERGY_FILE="/sys/class/powercap/intel-rapl:0/energy_uj"
MAX_RANGE=$(cat /sys/class/powercap/intel-rapl:0/max_energy_range_uj)
NUM_RUNS=25
# Use Slurm Job ID for the log file; defaults to 'manual' if run locally
LOG_FILE="batch_result_${SLURM_JOB_ID:-manual}.out"

# Initialize CSV header if it doesn't exist
if [ ! -f $CSV_FILE ]; then
    echo "Run_Number,Execution_Time_Sec_8_Cores,Total_Energy_J_8_Cores,Avg_Power_W_8_Cores" > $CSV_FILE
fi

# Function to sample energy in background (handles multi-wrap)
sample_energy() {
    local RUN_ID=$1
    local ACCUMULATED_UJ=0
    local PREV=$(cat $ENERGY_FILE)
    
    while [ -f .running_$RUN_ID ]; do
        CURRENT=$(cat $ENERGY_FILE)
        DIFF=$((CURRENT - PREV))
        # Handle wrap-around
        if [ "$(echo "$DIFF < 0" | bc)" -eq 1 ]; then
            DIFF=$(echo "$DIFF + $MAX_RANGE" | bc)
        fi
        ACCUMULATED_UJ=$((ACCUMULATED_UJ + DIFF))
        PREV=$CURRENT
        echo $ACCUMULATED_UJ > .energy_tmp_$RUN_ID
        sleep 10
    done
}

for ((i=1; i<=NUM_RUNS; i++))
do
    echo "Starting Run $i of $NUM_RUNS..." | tee -a "$LOG_FILE"
    
    # Capture energy BEFORE
    BEFORE_UJ=$(cat "$ENERGY_FILE")
    START_TIME=$(date +%s%N)
    
    # Run simulation
    $EXEC_WRAPPER mpirun -np 8 --map-by core --bind-to core --report-bindings ./miniMD_openmpi -i in.lj.miniMD >> $LOG_FILE 2>&1
    
    # Capture energy AFTER
    END_TIME=$(date +%s%N)
    AFTER_UJ=$(cat "$ENERGY_FILE")
    
    # Calculate difference (Handle wrap-around)
    DIFF_UJ=$(echo "$AFTER_UJ - $BEFORE_UJ" | bc)
    if [ "$(echo "$DIFF_UJ < 0" | bc)" -eq 1 ]; then
        DIFF_UJ=$(echo "$DIFF_UJ + $MAX_RANGE" | bc)
    fi
    
    # Calculations
    ELAPSED_NS=$(echo "$END_TIME - $START_TIME" | bc)
    TIME_SEC=$(echo "scale=3; $ELAPSED_NS / 1000000000" | bc)
    ENERGY_J=$(echo "scale=3; $DIFF_UJ / 1000000" | bc)
    POWER_W=$(echo "scale=2; $ENERGY_J / $TIME_SEC" | bc)
    
    # Save results
    echo "$i,$TIME_SEC,$ENERGY_J,$POWER_W" >> "$CSV_FILE"
    echo "Run $i finished: ${TIME_SEC}s, ${ENERGY_J}J" | tee -a "$LOG_FILE"
done