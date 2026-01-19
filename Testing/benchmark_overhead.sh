#!/bin/bash

# ================= CONFIGURATION =================
MPI_RANKS=30
PYTHON_SCRIPT="test.py"
RAPL_PATH="/sys/class/powercap/intel-rapl:0/energy_uj"
MAX_PATH="/sys/class/powercap/intel-rapl:0/max_energy_range_uj"

# CRITICAL FIX: Robust Input File Generation
# We take the original working file and force the size/steps change using wildcards (.*)
# This handles tabs, multiple spaces, or comments that might exist between numbers.
cp in.lj.miniMD in.fast
sed -i 's/128.*128.*128/64 64 64/' in.fast  # Replace size with 40 40 40
sed -i 's/2000/2000/' in.fast               # Replace steps with 1000

# Use the new file
MINIMD_ARGS="-i in.fast"

# Verify tools
if ! command -v bc &> /dev/null; then echo "Error: bc missing"; exit 1; fi
MAX_UJ=$(cat $MAX_PATH 2>/dev/null || echo "4294967295")

# Energy Monitor Function
monitor_energy() {
    local out_file=$1
    local pid_to_watch=$2
    local prev=$(cat $RAPL_PATH)
    local total_uj=0
    
    while kill -0 $pid_to_watch 2>/dev/null; do
        sleep 1
        local curr=$(cat $RAPL_PATH)
        local diff=0
        if (( $(echo "$curr < $prev" | bc) )); then
            diff=$(echo "($MAX_UJ - $prev) + $curr" | bc)
        else
            diff=$(echo "$curr - $prev" | bc)
        fi
        total_uj=$(echo "$total_uj + $diff" | bc)
        prev=$curr
    done
    echo "$total_uj / 1000000" | bc -l > $out_file
}

echo "=========================================================="
echo "   CAPSTONE OVERHEAD ANALYSIS: FINAL FIX"
echo "=========================================================="
echo "Configuration:"
echo "  Ranks: $MPI_RANKS"
echo "  Input: in.fast (Generated from in.lj.miniMD)"

# ================= RUN 1: BASELINE =================
echo ""
echo "[1/2] Starting BASELINE run..."
start_t=$(date +%s.%N)

# Using 'grep' to filter output so you only see the important steps
mpirun --oversubscribe -np $MPI_RANKS ./miniMD_openmpi $MINIMD_ARGS | grep --line-buffered "Step" &
APP_PID=$!

monitor_energy "energy_base.txt" $APP_PID &
MON_PID=$!

wait $APP_PID
# Wait for monitor to exit gracefully
wait $MON_PID 

end_t=$(date +%s.%N)
time_base=$(echo "$end_t - $start_t" | bc -l)
energy_base=$(cat energy_base.txt)

echo ""
echo "      Baseline Done."
echo "      Time:   $(printf "%.2f" $time_base) s"
echo "      Energy: $(printf "%.2f" $energy_base) J"


# ================= RUN 2: MONITORED =================
echo ""
echo "[2/2] Starting MONITORED run..."
start_t=$(date +%s.%N)

mpirun --oversubscribe -np $MPI_RANKS ./miniMD_openmpi $MINIMD_ARGS | grep --line-buffered "Step" &
APP_PID=$!

FULL_CMD="mpirun -np $MPI_RANKS ./miniMD_openmpi"
# Redirect python output to /dev/null to keep screen clean, or a log file if debugging
python3 $PYTHON_SCRIPT -n $MPI_RANKS -c "$FULL_CMD" > monitor_error.log 2>&1 &
PY_PID=$!

monitor_energy "energy_mon.txt" $APP_PID &
MON_PID=$!

wait $APP_PID
wait $MON_PID

# Stop the python script
kill $PY_PID 2>/dev/null

end_t=$(date +%s.%N)
time_mon=$(echo "$end_t - $start_t" | bc -l)
energy_mon=$(cat energy_mon.txt)

# Find the latest CSV
LATEST_CSV=$(ls -t monitor_v17_*.csv | head -n 1)

# Check for classification in the 'phase' column (Column 2)
echo "Phase summary for $LATEST_CSV:"
awk -F',' '{print $2}' "$LATEST_CSV" | sort | uniq -c

echo ""
echo "      Monitored Run Done."
echo "      Time:   $(printf "%.2f" $time_mon) s"
echo "      Energy: $(printf "%.2f" $energy_mon) J"

# ================= RESULTS =================
echo ""
echo "=========================================================="
echo "                  FINAL RESULTS"
echo "=========================================================="

time_pct=$(echo "(($time_mon - $time_base) / $time_base) * 100" | bc -l)
energy_pct=$(echo "(($energy_mon - $energy_base) / $energy_base) * 100" | bc -l)

echo "Runtime Overhead: $(printf "%+.2f" $time_pct)%"
echo "Energy Delta:     $(printf "%+.2f" $energy_pct)%" 
echo "=========================================================="