#!/bin/bash

# Configuration
CSV_FILE="simulation_results.csv"
ENERGY_FILE="/sys/class/powercap/intel-rapl:0/energy_uj"
MAX_RANGE=$(cat /sys/class/powercap/intel-rapl:0/max_energy_range_uj)
NUM_RUNS=20

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
    echo "Starting Run $i of $NUM_RUNS..."
    
    # Setup background monitoring
    touch .running_$i
    sample_energy $i &
    MONITOR_PID=$!
    
    START_TIME=$(date +%s%N)
    
    # Run the simulation
    mpirun --oversubscribe -np 16 ./miniMD_openmpi -i in.lj.miniMD > /dev/null 2>&1
    
    END_TIME=$(date +%s%N)
    
    # Cleanup monitoring
    rm .running_$i
    wait $MONITOR_PID
    
    # Calculations
    TOTAL_UJ=$(cat .energy_tmp_$i)
    ELAPSED_NS=$((END_TIME - START_TIME))
    
    # Formatting with bc
    TIME_SEC=$(echo "scale=3; $ELAPSED_NS / 1000000000" | bc)
    ENERGY_J=$(echo "scale=3; $TOTAL_UJ / 1000000" | bc)
    POWER_W=$(echo "scale=2; $ENERGY_J / $TIME_SEC" | bc)
    
    # Save to CSV
    echo "$i,$TIME_SEC,$ENERGY_J,$POWER_W" >> $CSV_FILE
    
    # Cleanup temp files
    rm .energy_tmp_$i
    
    echo "Run $i finished: ${TIME_SEC}s, ${ENERGY_J}J"
done

echo "All $NUM_RUNS runs completed. Data saved to $CSV_FILE."