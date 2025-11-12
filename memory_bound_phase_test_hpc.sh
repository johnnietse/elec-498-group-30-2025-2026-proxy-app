# # #!/bin/bash
# # # HPC-optimized memory-bound phase test using RAPL counters

# # echo "=== Memory-Bound Phase Testing on HPC ==="

# # # Set HPC environment
# # export OMP_NUM_THREADS=32
# # export KMP_AFFINITY=compact

# # # Function to read RAPL energy
# # read_rapl_energy() {
# #     local domain=$1
# #     local energy_uj=$(cat /sys/class/powercap/intel-rapl:${domain}/energy_uj 2>/dev/null || echo "0")
# #     echo $((energy_uj / 1000000)) # Convert to joules
# # }

# # # Function to run test with energy measurement
# # run_test_with_energy() {
# #     local test_name=$1
# #     local command=$2
# #     local output_log=$3
    
# #     echo "Starting $test_name..."
    
# #     # Read initial energy
# #     energy_pkg_start=$(read_rapl_energy "0")
# #     energy_dram_start=$(read_rapl_energy "0:2")
    
# #     # Start timer
# #     start_time=$(date +%s.%N)
    
# #     # Run the command
# #     $command
    
# #     # End timer
# #     end_time=$(date +%s.%N)
    
# #     # Read final energy
# #     energy_pkg_end=$(read_rapl_energy "0")
# #     energy_dram_end=$(read_rapl_energy "0:2")
    
# #     # Calculate metrics
# #     runtime=$(echo "$end_time - $start_time" | bc)
# #     energy_pkg_used=$((energy_pkg_end - energy_pkg_start))
# #     energy_dram_used=$((energy_dram_end - energy_dram_start))
    
# #     # Save results
# #     cat > $output_log << EOF
# # Test: $test_name
# # Runtime: $runtime seconds
# # Energy PKG: $energy_pkg_used J
# # Energy DRAM: $energy_dram_used J
# # Timestamp: $(date)
# # EOF

# #     echo "Completed $test_name: ${runtime}s, ${energy_pkg_used}J"
# # }

# # # echo "Running baseline memory-bound measurement..."
# # # run_test_with_energy "Memory-Bound Baseline" \
# # #     "../miniFE/openmp/src/miniFE.x -i input_memory_large.in -c config_memory.cfg" \
# # #     "memory_baseline.log"

# # # echo "Running optimized memory-bound measurement..."
# # # run_test_with_energy "Memory-Bound Optimized" \
# # #     "../miniFE/openmp/src/miniFE.x -i input_memory_large.in -c config_memory.cfg --power-optimize memory" \
# # #     "memory_optimized.log"


# # # Baseline
# # echo "Running baseline memory-bound measurement..."
# # run_test_with_energy "Memory-Bound Baseline" \
# #     "srun ./miniFE.x -i input_memory_large.in -c config_memory.cfg" \
# #     "memory_baseline.log"

# # # Optimized
# # echo "Running optimized memory-bound measurement..."
# # run_test_with_energy "Memory-Bound Optimized" \
# #     "srun ./miniFE.x -i input_memory_large.in -c config_memory.cfg --power-optimize memory" \
# #     "memory_optimized.log"


# # echo "Analyzing results..."
# # python3 memory_analysis.py memory_baseline.log memory_optimized.log

# # echo "Memory-bound phase testing completed!"

# #!/bin/bash
# # HPC-optimized memory-bound phase test using RAPL counters

# echo "=== Memory-Bound Phase Testing on HPC ==="

# # Set HPC environment
# export OMP_NUM_THREADS=32
# export KMP_AFFINITY=compact

# # Paths
# MINIFE_EXEC="$(pwd)/miniFE.x"  # assumes miniFE.x is in current folder
# INPUT_FILE="input_memory_large.in"
# CONFIG_FILE="config_memory.cfg"
# LOG_BASELINE="memory_baseline.log"
# LOG_OPTIMIZED="memory_optimized.log"

# # Check that miniFE executable exists
# if [ ! -f "$MINIFE_EXEC" ]; then
#     echo "Error: miniFE executable not found at $MINIFE_EXEC"
#     echo "Please build miniFE.x and place it in this directory"
#     exit 1
# fi

# # Function to read RAPL energy
# read_rapl_energy() {
#     local domain=$1
#     local energy_uj=$(cat /sys/class/powercap/intel-rapl:${domain}/energy_uj 2>/dev/null || echo "0")
#     echo $((energy_uj / 1000000)) # Convert microjoules to joules
# }

# # Function to run a test with energy measurement
# run_test_with_energy() {
#     local test_name=$1
#     local command=$2
#     local output_log=$3

#     echo "Starting $test_name..."

#     # Read initial energy
#     local energy_pkg_start=$(read_rapl_energy "0")
#     local energy_dram_start=$(read_rapl_energy "0:2")

#     # Start timer
#     local start_time=$(date +%s.%N)

#     # Run the command
#     eval "$command"

#     # End timer
#     local end_time=$(date +%s.%N)

#     # Read final energy
#     local energy_pkg_end=$(read_rapl_energy "0")
#     local energy_dram_end=$(read_rapl_energy "0:2")

#     # Calculate metrics
#     # local runtime=$(echo "$end_time - $start_time" | bc)
#     runtime=$(awk "BEGIN {print $end_time - $start_time}")
#     local energy_pkg_used=$((energy_pkg_end - energy_pkg_start))
#     local energy_dram_used=$((energy_dram_end - energy_dram_start))

#     # Save results
#     cat > "$output_log" << EOF
# Test: $test_name
# Runtime: $runtime seconds
# Energy PKG: $energy_pkg_used J
# Energy DRAM: $energy_dram_used J
# Timestamp: $(date)
# EOF

#     echo "Completed $test_name: Runtime=${runtime}s, Energy PKG=${energy_pkg_used}J, Energy DRAM=${energy_dram_used}J"
# }


# # Detect available cores automatically
# CORES=$(nproc)
# MPI_RANKS=$((CORES / 8))  # use 8 threads per rank
# export OMP_NUM_THREADS=8

# echo "Detected $CORES cores → using $MPI_RANKS MPI ranks × $OMP_NUM_THREADS threads"




# # # Run Baseline
# # run_test_with_energy "Memory-Bound Baseline" \
# #     "srun $MINIFE_EXEC -i $INPUT_FILE -c $CONFIG_FILE" \
# #     "$LOG_BASELINE"

# # # Run Optimized
# # run_test_with_energy "Memory-Bound Optimized" \
# #     "srun $MINIFE_EXEC -i $INPUT_FILE -c $CONFIG_FILE --power-optimize memory" \
# #     "$LOG_OPTIMIZED"


# # Run Baseline
# # run_test_with_energy "Memory-Bound Baseline" \
# #     "mpirun -np $OMP_NUM_THREADS $MINIFE_EXEC -i $INPUT_FILE -c $CONFIG_FILE" \
# #     "$LOG_BASELINE"


# # Run Optimized
# # run_test_with_energy "Memory-Bound Optimized" \
# #     "mpirun -np $OMP_NUM_THREADS $MINIFE_EXEC -i $INPUT_FILE -c $CONFIG_FILE --power-optimize memory" \
# #     "$LOG_OPTIMIZED"
# # memory_optimized.log


# # run_test_with_energy "Memory-Bound Baseline" \
# #     "mpirun -np 1 ./miniFE.x -- -i input_memory_large.in -c config_memory.cfg" \
# #     "memory_baseline.log"

# # run_test_with_energy "Memory-Bound Optimized" \
# #     "mpirun -np 1 ./miniFE.x -- -i input_memory_large.in -c config_memory.cfg --power-optimize memory" \
# #     "memory_optimized.log"
# #     # "$LOG_OPTIMIZED"


# # Run Baseline with perf
# run_test_with_energy "Memory-Bound Baseline" \
#     "perf stat -e power/energy-pkg/,power/energy-ram/,cache-references,cache-misses,instructions,cpu-cycles ./miniFE.x -i input_memory_large.in -c config_memory.cfg 2> memory_baseline.log" \
#     "memory_baseline.log"

# # Run Optimized with perf
# run_test_with_energy "Memory-Bound Optimized" \
#     "perf stat -e power/energy-pkg/,power/energy-ram/,cache-references,cache-misses,instructions,cpu-cycles ./miniFE.x -i input_memory_large.in -c config_memory.cfg --power-optimize memory 2> memory_optimized.log" \
#     "memory_optimized.log"



# # Analyze results using Python
# if [ -f memory_analysis.py ]; then
#     echo "Analyzing results..."
#     # python3 memory_analysis.py "$LOG_BASELINE" "$LOG_OPTIMIZED"
#     python3 memory_analysis.py memory_baseline.log memory_optimized.log

# else
#     echo "Warning: memory_analysis.py not found, skipping analysis"
# fi

# echo "Memory-bound phase testing completed!"


# Working script below!

#!/bin/bash
# HPC-optimized memory-bound phase test using perf and RAPL


echo "=== Memory-Bound Phase Testing on HPC ==="

mpirun ./miniFE.x --nx 32 --ny 32 --nx 32 --num_steps 10

# Environment setup
export OMP_NUM_THREADS=8
export KMP_AFFINITY=compact

MINIFE_EXEC="./miniFE.x"
INPUT_FILE="input_memory_5000.in"
CONFIG_FILE="config_memory.cfg"

# Check executable
if [ ! -f "$MINIFE_EXEC" ]; then
    echo "Error: miniFE executable not found!"
    exit 1
fi

run_perf_test() {
    local test_name=$1
    local command=$2
    local output_log=$3

    echo "Starting $test_name..."
    start_time=$(date +%s.%N)

    eval "$command"

    end_time=$(date +%s.%N)
    runtime=$(awk "BEGIN {print $end_time - $start_time}")

    # runtime=$( { /usr/bin/time -f "%e" eval "$command"; } 2>&1 )

    echo "Runtime: $runtime seconds" >> "$output_log"
    echo "Completed $test_name"
}


# Baseline
run_perf_test "Memory-Bound Baseline" \
    "perf stat -e power/energy-pkg/,power/energy-ram/,cache-references,cache-misses,instructions,cpu-cycles $MINIFE_EXEC -i $INPUT_FILE -c $CONFIG_FILE --problem-size 5000 2> memory_baseline.log" \
    "memory_baseline.log"

# Optimized
run_perf_test "Memory-Bound Optimized" \
    "perf stat -e power/energy-pkg/,power/energy-ram/,cache-references,cache-misses,instructions,cpu-cycles $MINIFE_EXEC -i $INPUT_FILE -c $CONFIG_FILE --power-optimize memory --problem-size 5000 2> memory_optimized.log" \
    "memory_optimized.log"

# Analysis
if [ -f memory_analysis.py ]; then
    echo "Analyzing results..."
    python3 memory_analysis.py memory_baseline.log memory_optimized.log
else
    echo "Warning: memory_analysis.py not found, skipping analysis"
fi

echo "Memory-bound phase testing completed!"
