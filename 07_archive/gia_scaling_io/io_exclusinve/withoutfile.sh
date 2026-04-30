#!/bin/bash
#SBATCH --job-name=ckpt_freq_full
#SBATCH --output=checkpoint_freq_full_%j.out
#SBATCH --nodes=1
#SBATCH --ntasks=4                    # Number of MPI ranks
#SBATCH --cpus-per-task=1
#SBATCH --time=4:00:00
#SBATCH --mem=8G
#SBATCH --exclusive
#SBATCH --constraint=lkb
#SBATCH --cpu-freq=performance        # We'll override this manually
#SBATCH --partition=gpu-rgrant
#SBATCH --mail-user=19jl253@queensu.ca
#SBATCH --mail-type=END,FAIL

# ==========================================
# FULL CHECKPOINT FREQUENCY EXPERIMENT
# Tests: 1.2 GHz, 1.6 GHz, 2.0 GHz
# WITH: Monitoring, frequency tracking, I/O detection
# USING: cpupower (like your friend's method!)
# ==========================================

export OMP_NUM_THREADS=1

CORES=$SLURM_NTASKS
NUM_RUNS=5

echo "=========================================="
echo "Full Checkpoint Frequency Experiment"
echo "Using cpupower for frequency control"
echo "Cores: $CORES"
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $(hostname)"
echo "Date: $(date)"
echo "=========================================="

# Available frequencies (in kHz for sysfs)
FREQ_1200_KHZ="1200000"  # 1.2 GHz
FREQ_1600_KHZ="1600000"  # 1.6 GHz
FREQ_2000_KHZ="2000000"  # 2.0 GHz

TOTAL_CORES=$(nproc)

# Energy monitoring
ENERGY_FILE="/sys/class/powercap/intel-rapl:0/energy_uj"
MAX_RANGE_FILE="/sys/class/powercap/intel-rapl:0/max_energy_range_uj"
FREQ_FILE="/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq"

# ==========================================
# CHECK SYSFS FREQUENCY CONTROL AVAILABILITY
# ==========================================

echo ""
echo "Checking for sysfs CPU frequency control..."

GOV_FILE="/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"
SETSPEED_FILE="/sys/devices/system/cpu/cpu0/cpufreq/scaling_setspeed"

if [ ! -f "$GOV_FILE" ]; then
    echo "ERROR: $GOV_FILE not found!"
    echo "CPU frequency control via sysfs is not available on this node."
    exit 1
fi

# Switch to userspace governor
echo "userspace" > "$GOV_FILE" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "ERROR: Cannot write to $GOV_FILE (permission denied)"
    echo "This node does not allow user-level frequency control."
    exit 1
fi

echo "✓ Governor set to userspace"

# Test setting a frequency
echo "1200000" > "$SETSPEED_FILE" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "ERROR: Cannot write to $SETSPEED_FILE (permission denied)"
    exit 1
fi

echo "✓ sysfs frequency control is working"
echo ""

# ==========================================
# CHECK FILES
# ==========================================

if [ ! -f miniMD_openmpi ]; then
    echo "ERROR: miniMD_openmpi not found!"
    exit 1
fi

# Check for monitoring script
MONITORING_SCRIPT=""
if [ -f monitoring_enhanced.py ]; then
    MONITORING_SCRIPT="monitoring_enhanced.py"
    echo "Found monitoring script: monitoring_enhanced.py (enhanced)"
    chmod +x monitoring_enhanced.py
elif [ -f monitoring_fixed.py ]; then
    MONITORING_SCRIPT="monitoring_fixed.py"
    echo "Found monitoring script: monitoring_fixed.py (standard)"
    chmod +x monitoring_fixed.py
else
    echo "WARNING: No monitoring script found!"
    echo "Looking for: monitoring_fixed.py or monitoring_enhanced.py"
    echo "Continuing without I/O monitoring..."
fi

# Setup checkpoint directory - REQUIRE lscratch
if [ -n "$SLURM_TMPDIR" ] && [ -d "$SLURM_TMPDIR" ]; then
    CKPT_DIR="$SLURM_TMPDIR/chk"
    mkdir -p "$CKPT_DIR"
    rm -rf chk
    ln -s "$CKPT_DIR" chk
    echo "Using /lscratch: $CKPT_DIR"
else
    echo ""
    echo "=========================================="
    echo "ERROR: lscratch (/lscratch) is NOT available!"
    echo "=========================================="
    echo ""
    echo "SLURM_TMPDIR is not set or does not exist."
    echo "This script requires fast local storage for checkpoint I/O."
    echo ""
    echo "Solutions:"
    echo "  1. Make sure your partition supports lscratch"
    echo "  2. Check with: sinfo -o '%P %f' | grep lscratch"
    echo "  3. Try a different partition (e.g., --partition=compute)"
    echo ""
    echo "Current SLURM_TMPDIR: ${SLURM_TMPDIR:-<not set>}"
    echo ""
    echo "Job will now exit."
    echo "=========================================="
    exit 1
fi

echo "Symlink check:"
ls -lh chk
echo ""

# ==========================================
# CPU INFO
# ==========================================

echo "CPU Frequency Information:"
echo "  Model: $(lscpu | grep 'Model name' | cut -d: -f2 | xargs)"
echo "  Total Cores: $TOTAL_CORES"

# Get available frequencies from cpupower
echo ""
echo "Available frequencies (from cpupower):"
cpupower frequency-info 2>/dev/null | grep "available frequency steps" || echo "  Could not determine available frequencies"

FREQ_MIN=$(cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_min_freq 2>/dev/null || echo "N/A")
FREQ_MAX=$(cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq 2>/dev/null || echo "N/A")
echo "  Available Range: $((FREQ_MIN/1000)) - $((FREQ_MAX/1000)) MHz"

if [ -f "$FREQ_FILE" ]; then
    CURRENT_FREQ_KHZ=$(cat "$FREQ_FILE")
    CURRENT_FREQ_MHZ=$((CURRENT_FREQ_KHZ / 1000))
    echo "  Current Frequency: ${CURRENT_FREQ_MHZ} MHz"
    
    GOV_FILE="/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"
    if [ -f "$GOV_FILE" ]; then
        GOVERNOR=$(cat "$GOV_FILE")
        echo "  Governor: $GOVERNOR"
    fi
else
    echo "  Frequency monitoring: NOT AVAILABLE"
fi

echo ""

# ==========================================
# FREQUENCY CONTROL FUNCTIONS (using cpupower!)
# ==========================================

set_all_cores_frequency() {
    local target_freq_khz=$1  # e.g., "1200000"
    local freq_name=$2        # e.g., "1200MHz"

    echo "Setting all cores to ${freq_name} using sysfs..."

    local set_count=0
    local fail_count=0

    for (( core=0; core<TOTAL_CORES; core++ )); do
        local gov_file="/sys/devices/system/cpu/cpu${core}/cpufreq/scaling_governor"
        local set_file="/sys/devices/system/cpu/cpu${core}/cpufreq/scaling_setspeed"

        # Ensure userspace governor
        echo "userspace" > "$gov_file" 2>/dev/null

        # Set frequency
        echo "$target_freq_khz" > "$set_file" 2>/dev/null
        if [ $? -eq 0 ]; then
            ((set_count++))
        else
            ((fail_count++))
        fi
    done

    echo "  Successfully set: $set_count cores"
    if [ $fail_count -gt 0 ]; then
        echo "  Failed: $fail_count cores"
    fi

    sleep 0.5

    # Verify frequency was actually set
    local actual_freq=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq 2>/dev/null || echo "0")
    local actual_mhz=$((actual_freq / 1000))
    echo "  Verified frequency: ${actual_mhz} MHz"

    return $([ $set_count -gt 0 ] && echo 0 || echo 1)
}

reset_frequencies() {
    echo "Resetting CPU frequencies to default (performance governor)..."

    for (( core=0; core<TOTAL_CORES; core++ )); do
        echo "performance" > "/sys/devices/system/cpu/cpu${core}/cpufreq/scaling_governor" 2>/dev/null
    done

    echo "  ✓ Reset to performance governor"
}

# ==========================================
# FREQUENCY SAMPLING (Background)
# ==========================================

sample_frequency() {
    local RUN_ID=$1
    local SAMPLE_FILE=".freq_samples_${RUN_ID}"
    
    > "$SAMPLE_FILE"  # Clear file
    
    while [ -f ".running_${RUN_ID}" ]; do
        if [ -f "$FREQ_FILE" ]; then
            FREQ_KHZ=$(cat "$FREQ_FILE" 2>/dev/null || echo "0")
            FREQ_MHZ=$((FREQ_KHZ / 1000))
            TIMESTAMP=$(date +%s.%N)
            echo "$TIMESTAMP $FREQ_MHZ" >> "$SAMPLE_FILE"
        fi
        sleep 0.5
    done
}

# ==========================================
# ENERGY MEASUREMENT
# ==========================================

read_energy() {
    cat "$ENERGY_FILE" 2>/dev/null || echo "0"
}

calculate_energy() {
    local start_uj=$1
    local end_uj=$2
    local max_range=$(cat "$MAX_RANGE_FILE" 2>/dev/null || echo "262143328850")
    
    local diff_uj=$((end_uj - start_uj))
    
    if [ $diff_uj -lt 0 ]; then
        diff_uj=$((diff_uj + max_range))
    fi
    
    echo "scale=3; $diff_uj / 1000000" | bc -l
}

# ==========================================
# RUN EXPERIMENT AT FREQUENCY
# ==========================================

run_at_frequency() {
    local freq_ghz=$1      # e.g., "1200000" (kHz)
    local freq_name=$2     # e.g., "1200MHz"
    local run=$3
    
    echo ""
    echo "=========================================="
    echo "Frequency: ${freq_name} | Run: $run/$NUM_RUNS"
    echo "=========================================="
    
    # Set frequency using sysfs
    set_all_cores_frequency "$freq_ghz" "$freq_name"
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to set frequency for ${freq_name}"
        echo "Skipping this run..."
        return 1
    fi
    
    sleep 2
    
    # Clean checkpoint directory
    rm -rf "$CKPT_DIR"/*
    mkdir -p "$CKPT_DIR"
    rm -f storage_io_phaseA.csv
    
    # Pre-run measurements
    echo ""
    echo "Pre-run measurements:"
    
    DISK_BEFORE=$(du -sb "$CKPT_DIR" 2>/dev/null | awk '{print $1}')
    [ -z "$DISK_BEFORE" ] && DISK_BEFORE=0
    echo "  Disk usage: $DISK_BEFORE bytes"
    
    BEFORE_UJ=$(read_energy)
    echo "  Energy counter: $BEFORE_UJ uJ"
    
    if [ -f "$FREQ_FILE" ]; then
        FREQ_BEFORE_KHZ=$(cat "$FREQ_FILE")
        FREQ_BEFORE_MHZ=$((FREQ_BEFORE_KHZ / 1000))
        echo "  CPU Frequency: ${FREQ_BEFORE_MHZ} MHz"
    fi
    echo ""
    
    # Generate unique run ID for this frequency and run
    RUN_ID="${freq_name}_run${run}"
    
    # Start frequency sampling in background
    touch ".running_${RUN_ID}"
    sample_frequency "$RUN_ID" &
    FREQ_SAMPLER_PID=$!
    
    # Start monitoring if available
    if [ -n "$MONITORING_SCRIPT" ]; then
        echo "Starting $MONITORING_SCRIPT..."
        python3 $MONITORING_SCRIPT &
        MONITOR_PID=$!
        sleep 2
    fi
    
    # Record start time
    START_TIME_NS=$(date +%s%N)
    
    echo "Starting miniMD with $CORES cores..."
    echo "Command: mpirun -np $CORES --bind-to core ./miniMD_openmpi -i in.lj.miniMD --ckpt_io_duration 30 --ckpt_chunk_mb 1 --ckpt_sleep_ms 100 --ckpt_dir $CKPT_DIR"
    echo ""
    
    # Run miniMD
    mpirun -np $CORES --bind-to core ./miniMD_openmpi -i in.lj.miniMD \
        --ckpt_io_duration 30 \
        --ckpt_chunk_mb 1 \
        --ckpt_sleep_ms 100 \
        --ckpt_dir "$CKPT_DIR" 2>&1 | tee "minimd_${freq_name}_run${run}.log"
    
    MINIMD_EXIT=$?
    
    # Record end time and energy
    END_TIME_NS=$(date +%s%N)
    AFTER_UJ=$(read_energy)
    
    # Stop frequency sampling
    rm -f ".running_${RUN_ID}"
    wait $FREQ_SAMPLER_PID 2>/dev/null
    
    # Stop monitoring
    if [ -n "$MONITOR_PID" ]; then
        kill $MONITOR_PID 2>/dev/null
        wait $MONITOR_PID 2>/dev/null
    fi
    
    echo ""
    echo "miniMD exit code: $MINIMD_EXIT"
    
    if [ $MINIMD_EXIT -ne 0 ]; then
        echo "ERROR: miniMD failed!"
        return 1
    fi
    
    # Post-run measurements
    echo ""
    echo "Post-run measurements:"
    
    DISK_AFTER=$(du -sb "$CKPT_DIR" 2>/dev/null | awk '{print $1}')
    [ -z "$DISK_AFTER" ] && DISK_AFTER=$DISK_BEFORE
    echo "  Disk usage: $DISK_AFTER bytes"
    
    DISK_WRITTEN_BYTES=$((DISK_AFTER - DISK_BEFORE))
    CHECKPOINT_MB=$(echo "scale=2; $DISK_WRITTEN_BYTES / 1048576" | bc -l)
    echo "  Checkpoint size: ${CHECKPOINT_MB} MB"
    
    # Count checkpoint files
    NUM_FILES=$(find "$CKPT_DIR" -type f -name "*.bin" 2>/dev/null | wc -l)
    echo "  Number of .bin files: $NUM_FILES"
    
    # Energy calculation
    ENERGY_J=$(calculate_energy "$BEFORE_UJ" "$AFTER_UJ")
    echo "  Energy consumed: ${ENERGY_J} J"
    
    # Time calculation
    ELAPSED_NS=$(echo "$END_TIME_NS - $START_TIME_NS" | bc)
    TIME_SEC=$(echo "scale=3; $ELAPSED_NS / 1000000000" | bc -l)
    echo "  Execution time: ${TIME_SEC} s"
    
    # Power calculation
    if [ $(echo "$TIME_SEC > 0" | bc -l) -eq 1 ]; then
        POWER_W=$(echo "scale=2; $ENERGY_J / $TIME_SEC" | bc -l)
        echo "  Average power: ${POWER_W} W"
    else
        POWER_W="0"
        echo "  Average power: 0 W (time too short)"
    fi
    
    # Process frequency samples
    if [ -f ".freq_samples_${RUN_ID}" ]; then
        AVG_FREQ=$(awk '{sum+=$2; count++} END {if(count>0) print int(sum/count); else print 0}' ".freq_samples_${RUN_ID}")
        MIN_FREQ=$(awk 'BEGIN{min=999999} {if($2<min && $2>0) min=$2} END {print int(min)}' ".freq_samples_${RUN_ID}")
        MAX_FREQ=$(awk 'BEGIN{max=0} {if($2>max) max=$2} END {print int(max)}' ".freq_samples_${RUN_ID}")
        
        echo "  CPU Frequency during run:"
        echo "    Average: ${AVG_FREQ} MHz"
        echo "    Min: ${MIN_FREQ} MHz"
        echo "    Max: ${MAX_FREQ} MHz"
        
        # Archive frequency data
        mv ".freq_samples_${RUN_ID}" "freq_samples_${freq_name}_${CORES}cores_run${run}_${SLURM_JOB_ID}.txt"
    else
        AVG_FREQ=0
        MIN_FREQ=0
        MAX_FREQ=0
        echo "  CPU Frequency: Not available"
    fi
    
    # Check I/O detection from monitoring
    IO_DETECTED="NO"
    if [ -f storage_io_phaseA.csv ]; then
        IO_COUNT=$(grep -c "CHECKPOINT_IO" storage_io_phaseA.csv 2>/dev/null || echo "0")
        if [ "$IO_COUNT" -gt 0 ]; then
            IO_DETECTED="YES"
            echo "  I/O Phase Detected: YES ($IO_COUNT samples)"
        else
            echo "  I/O Phase Detected: NO"
        fi
        
        # Archive monitoring data
        mv storage_io_phaseA.csv "monitoring_${freq_name}_${CORES}cores_run${run}_${SLURM_JOB_ID}.csv"
    else
        echo "  I/O Phase Detected: N/A (no monitoring)"
    fi
    
    # Show checkpoint directory
    echo ""
    echo "Checkpoint directory contents:"
    ls -lh "$CKPT_DIR" | head -20
    echo ""
    du -sh "$CKPT_DIR"
    
    # Archive checkpoint files
    echo ""
    echo "Archiving checkpoint files..."
    ARCHIVE_DIR="checkpoint_bins_${freq_name}_run${run}_${SLURM_JOB_ID}"
    mkdir -p "$ARCHIVE_DIR"
    
    if [ "$NUM_FILES" -gt 0 ]; then
        cp "$CKPT_DIR"/*.bin "$ARCHIVE_DIR/" 2>/dev/null
        echo "  Copied to: $ARCHIVE_DIR/"
    fi
    
    # Archive miniMD log
    [ -f "minimd_${freq_name}_run${run}.log" ] && \
        mv "minimd_${freq_name}_run${run}.log" "minimd_${freq_name}_${CORES}cores_run${run}_${SLURM_JOB_ID}.log"
    
    echo ""
    echo "Summary: ${TIME_SEC}s, ${ENERGY_J}J, ${POWER_W}W, ${CHECKPOINT_MB}MB, Freq: ${AVG_FREQ}/${MIN_FREQ}/${MAX_FREQ} MHz, I/O: ${IO_DETECTED}"
    
    # Return CSV data
    echo "$run,$TIME_SEC,$ENERGY_J,$POWER_W,$CHECKPOINT_MB,$AVG_FREQ,$MIN_FREQ,$MAX_FREQ,$IO_DETECTED,$NUM_FILES"
}

# ==========================================
# MAIN EXPERIMENT LOOP
# ==========================================

CSV_1200="results_1200MHz_${CORES}cores_${SLURM_JOB_ID}.csv"
CSV_1600="results_1600MHz_${CORES}cores_${SLURM_JOB_ID}.csv"
CSV_2000="results_2000MHz_${CORES}cores_${SLURM_JOB_ID}.csv"

# CSV headers (same as original detailed script)
CSV_HEADER="Run,Time_Sec,Energy_J,Power_W,Checkpoint_MB,Avg_Freq_MHz,Min_Freq_MHz,Max_Freq_MHz,IO_Detected,Num_Files"
echo "$CSV_HEADER" > "$CSV_1200"
echo "$CSV_HEADER" > "$CSV_1600"
echo "$CSV_HEADER" > "$CSV_2000"

echo ""
echo "=========================================="
echo "Starting Experiments: $NUM_RUNS runs per frequency"
echo "=========================================="

for run in $(seq 1 $NUM_RUNS); do
    
    # 1.2 GHz
    echo ""
    echo "######################################################"
    echo "# Testing 1.2 GHz - Run $run/$NUM_RUNS"
    echo "######################################################"
    
    CSV_LINE=$(run_at_frequency "$FREQ_1200_KHZ" "1200MHz" "$run")
    if [ $? -eq 0 ]; then
        echo "$CSV_LINE" >> "$CSV_1200"
    fi
    
    sleep 3
    
    # 1.6 GHz
    echo ""
    echo "######################################################"
    echo "# Testing 1.6 GHz - Run $run/$NUM_RUNS"
    echo "######################################################"
    
    CSV_LINE=$(run_at_frequency "$FREQ_1600_KHZ" "1600MHz" "$run")
    if [ $? -eq 0 ]; then
        echo "$CSV_LINE" >> "$CSV_1600"
    fi
    
    sleep 3
    
    # 2.0 GHz
    echo ""
    echo "######################################################"
    echo "# Testing 2.0 GHz - Run $run/$NUM_RUNS"
    echo "######################################################"
    
    CSV_LINE=$(run_at_frequency "$FREQ_2000_KHZ" "2000MHz" "$run")
    if [ $? -eq 0 ]; then
        echo "$CSV_LINE" >> "$CSV_2000"
    fi
    
    sleep 3
done

# ==========================================
# FINAL SUMMARY
# ==========================================

reset_frequencies

echo ""
echo "=========================================="
echo "EXPERIMENT COMPLETE"
echo "=========================================="

for freq_name in "1.2 GHz" "1.6 GHz" "2.0 GHz"; do
    if [ "$freq_name" == "1.2 GHz" ]; then
        CSV_FILE="$CSV_1200"
    elif [ "$freq_name" == "1.6 GHz" ]; then
        CSV_FILE="$CSV_1600"
    else
        CSV_FILE="$CSV_2000"
    fi
    
    echo ""
    echo "Results for $freq_name:"
    cat "$CSV_FILE"
    echo ""
    awk -F',' 'NR>1 {
        time+=$2; energy+=$3; power+=$4; ckpt+=$5; 
        freq_avg+=$6; freq_min+=$7; freq_max+=$8; count++
    } END {
        if(count>0) {
            printf "Averages:\n"
            printf "  Time: %.2f s\n", time/count
            printf "  Energy: %.2f J\n", energy/count
            printf "  Power: %.2f W\n", power/count
            printf "  Checkpoint: %.2f MB\n", ckpt/count
            printf "  Freq (Avg/Min/Max): %.0f / %.0f / %.0f MHz\n", freq_avg/count, freq_min/count, freq_max/count
            printf "  Runs completed: %d\n", count
        }
    }' "$CSV_FILE"
done

echo ""
echo "=========================================="
echo "Output Files:"
echo "  CSV Results:"
echo "    - $CSV_1200"
echo "    - $CSV_1600"
echo "    - $CSV_2000"
echo "  Job Log: checkpoint_freq_full_${SLURM_JOB_ID}.out"
echo "  Checkpoint bins: checkpoint_bins_*MHz_run*_${SLURM_JOB_ID}/"
echo "  Frequency samples: freq_samples_*MHz_*cores_run*_${SLURM_JOB_ID}.txt"
echo "  Monitoring data: monitoring_*MHz_*cores_run*_${SLURM_JOB_ID}.csv"
echo "  miniMD logs: minimd_*MHz_*cores_run*_${SLURM_JOB_ID}.log"
echo "=========================================="

# ==========================================
# CREATE TARBALL OF ALL RESULTS
# ==========================================

echo ""
echo "=========================================="
echo "Creating results tarball..."
echo "=========================================="

TARBALL_NAME="results_freq_${CORES}cores_${SLURM_JOB_ID}.tar.gz"

# Build list of files to include
FILES_TO_TAR=""

# CSV results
FILES_TO_TAR="$FILES_TO_TAR $CSV_1200 $CSV_1600 $CSV_2000"

# Job output log (if exists)
if [ -f "checkpoint_freq_full_${SLURM_JOB_ID}.out" ]; then
    FILES_TO_TAR="$FILES_TO_TAR checkpoint_freq_full_${SLURM_JOB_ID}.out"
fi

# Monitoring data
for freq in "1200MHz" "1600MHz" "2000MHz"; do
    for file in monitoring_${freq}_${CORES}cores_run*_${SLURM_JOB_ID}.csv; do
        [ -f "$file" ] && FILES_TO_TAR="$FILES_TO_TAR $file"
    done
done

# miniMD logs
for freq in "1200MHz" "1600MHz" "2000MHz"; do
    for file in minimd_${freq}_${CORES}cores_run*_${SLURM_JOB_ID}.log; do
        [ -f "$file" ] && FILES_TO_TAR="$FILES_TO_TAR $file"
    done
done

# Frequency samples
for freq in "1200MHz" "1600MHz" "2000MHz"; do
    for file in freq_samples_${freq}_${CORES}cores_run*_${SLURM_JOB_ID}.txt; do
        [ -f "$file" ] && FILES_TO_TAR="$FILES_TO_TAR $file"
    done
done



# Create tarball
echo "Compressing files..."
tar -czf "$TARBALL_NAME" $FILES_TO_TAR 2>/dev/null

if [ $? -eq 0 ]; then
    TARBALL_SIZE=$(du -h "$TARBALL_NAME" | awk '{print $1}')
    echo "  Created: $TARBALL_NAME (${TARBALL_SIZE})"
    
    # Copy to home directory
    echo ""
    echo "Copying tarball to home directory..."
    cp "$TARBALL_NAME" ~/
    
    if [ $? -eq 0 ]; then
        echo "  ✓ Successfully copied to: ~/$TARBALL_NAME"
        echo ""
        echo "To extract on another machine:"
        echo "  tar -xzf $TARBALL_NAME"
    else
        echo "  ✗ Failed to copy to home directory"
    fi
    
    # List contents
    echo ""
    echo "Tarball contents:"
    tar -tzf "$TARBALL_NAME" | head -30
    NUM_FILES=$(tar -tzf "$TARBALL_NAME" | wc -l)
    if [ $NUM_FILES -gt 30 ]; then
        echo "... and $((NUM_FILES - 30)) more files"
    fi
    echo "Total: $NUM_FILES items"
    
else
    echo "  ✗ Failed to create tarball"
fi

echo ""
echo "=========================================="
echo "EXPERIMENT COMPLETE!"
echo "=========================================="
echo ""
echo "Quick commands for next steps:"
echo ""
echo "# Copy tarball from home to local machine:"
echo "  scp hpc6084@login1:~/$TARBALL_NAME ."
echo ""
echo "# Or analyze results on cluster:"
echo "  python3 analyze_freq_results.py ${SLURM_JOB_ID}"
echo ""
echo "=========================================="
