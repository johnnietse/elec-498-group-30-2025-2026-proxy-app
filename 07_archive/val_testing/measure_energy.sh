#!/bin/bash
ENERGY_FILE="/sys/class/powercap/intel-rapl:0/energy_uj"
MAX_RANGE=$(cat /sys/class/powercap/intel-rapl:0/max_energy_range_uj)

TOTAL_ACCUMULATED_ENERGY=0
PREV_ENERGY=$(cat $ENERGY_FILE)

# Function to sample energy in the background
sample_energy() {
    while [ -f .job_running ]; do
        CURRENT_ENERGY=$(cat $ENERGY_FILE)
        
        # Calculate delta
        DIFF=$((CURRENT_ENERGY - PREV_ENERGY))
        
        # Handle wrap-around
        if [ $DIFF -lt 0 ]; then
            DIFF=$((DIFF + MAX_RANGE))
        fi
        
        TOTAL_ACCUMULATED_ENERGY=$((TOTAL_ACCUMULATED_ENERGY + DIFF))
        PREV_ENERGY=$CURRENT_ENERGY
        
        # Save to a temporary file so the main script can read it
        echo $TOTAL_ACCUMULATED_ENERGY > .total_energy_tmp
        sleep 30
    done
}

# Start the background sampler
touch .job_running
sample_energy &
SAMPLER_PID=$!

START_TIME=$(date +%s%N)

# RUN THE SIMULATION
mpirun -np 16 ./miniMD_openmpi -i in.lj.miniMD

END_TIME=$(date +%s%N)

# Stop the sampler
rm .job_running
wait $SAMPLER_PID 2>/dev/null

# Final Read
FINAL_TOTAL_UJ=$(cat .total_energy_tmp)
TOTAL_J=$(echo "scale=3; $FINAL_TOTAL_UJ / 1000000" | bc)
ELAPSED_SEC=$(echo "scale=3; ($END_TIME - $START_TIME) / 1000000000" | bc)
AVG_WATTS=$(echo "scale=2; $TOTAL_J / $ELAPSED_SEC" | bc)

echo "---------------------------------------"
echo "Corrected 16-Core Results:"
echo "Execution Time: $ELAPSED_SEC seconds"
echo "Total Energy:   $TOTAL_J Joules"
echo "Average Power:  $AVG_WATTS Watts"
echo "---------------------------------------"