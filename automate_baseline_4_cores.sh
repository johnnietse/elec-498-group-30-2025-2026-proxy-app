#!/bin/bash

# Configuration
CSV_FILE="4_cores_simulation_results.csv"
ENERGY_FILE="/sys/class/powercap/intel-rapl:0/energy_uj"
MAX_RANGE=$(cat /sys/class/powercap/intel-rapl:0/max_energy_range_uj)
NUM_RUNS=25
# Use Slurm Job ID for the log file; defaults to 'manual' if run locally
LOG_FILE="batch_result_${SLURM_JOB_ID:-manual}.out"

# Initialize CSV header if it doesn't exist
if [ ! -f $CSV_FILE ]; then
    echo "Run_Number,Execution_Time_Sec,Total_Energy_J,Avg_Power_W" > $CSV_FILE
fi

# Function to sample energy in background (handles multi-wrap)
sample_energy() {
    local RUN_ID=$1
    local ACCUMULATED_UJ=0
    local PREV=$(cat $ENERGY_FILE)
    
    while [ -f .running_$RUN_ID ]; do
        CURRENT=$(cat $ENERGY_FILE)
        DIFF=$((CURRENT - PREV))
        if [ $DIFF -lt 0 ]; then DIFF=$((DIFF + MAX_RANGE)); fi
        ACCUMULATED_UJ=$((ACCUMULATED_UJ + DIFF))
        PREV=$CURRENT
        echo $ACCUMULATED_UJ > .energy_tmp_$RUN_ID
        sleep 10
    done
}

for ((i=1; i<=NUM_RUNS; i++))
do
    echo "---------------------------------------" >> $LOG_FILE
    echo "Starting Run $i of $NUM_RUNS..." | tee -a $LOG_FILE
    
    # Setup background monitoring
    touch .running_$i
    sample_energy $i &
    MONITOR_PID=$!
    
    # Initialization buffer: prevents "file not found" errors
    sleep 2
    
    START_TIME=$(date +%s%N)
    
    # Run the simulation: capture miniMD physics output to the log file
    echo "--- miniMD Physics Output ---" >> $LOG_FILE
    mpirun --oversubscribe -np 4 ./miniMD_openmpi -i in.lj.miniMD >> $LOG_FILE 2>&1
    
    END_TIME=$(date +%s%N)
    
    # Cleanup monitoring with a small buffer to ensure the last energy write finishes
    sleep 1
    rm .running_$i
    wait $MONITOR_PID
    
    # Calculations with error checking
    if [ -f .energy_tmp_$i ]; then
        TOTAL_UJ=$(cat .energy_tmp_$i)
        ELAPSED_NS=$((END_TIME - START_TIME))
        
        # Formatting with bc
        TIME_SEC=$(echo "scale=3; $ELAPSED_NS / 1000000000" | bc)
        ENERGY_J=$(echo "scale=3; $TOTAL_UJ / 1000000" | bc)
        POWER_W=$(echo "scale=2; $ENERGY_J / $TIME_SEC" | bc)
        
        # Save to CSV
        echo "$i,$TIME_SEC,$ENERGY_J,$POWER_W" >> $CSV_FILE
        
        # Append summary to log file
        echo "Run $i Stats: ${TIME_SEC}s, ${ENERGY_J}J, ${POWER_W}W" >> $LOG_FILE
        echo "Run $i finished: ${TIME_SEC}s, ${ENERGY_J}J"
    else
        echo "ERROR: Energy data missing for Run $i" | tee -a $LOG_FILE
    fi
    
    # Cleanup temp files
    rm -f .energy_tmp_$i
done

echo "All $NUM_RUNS runs completed. Data saved to $CSV_FILE." | tee -a $LOG_FILE