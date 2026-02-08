#!/bin/bash
#SBATCH --job-name=miniMD_scaling
#SBATCH --output=scaling_results_%j.out
#SBATCH --nodes=1
#SBATCH --cpus-per-task=1
#SBATCH --time=48:00:00
#SBATCH --mem=64G             # Increased memory to support all runs
#SBATCH --exclusive           # Ensures no noise from other users
#SBATCH --partition=gpu-rgrant
#SBATCH --mail-user=20wyvs@queensu.ca
#SBATCH --mail-type=END,FAIL
#SBATCH --cpu-freq=performance        # Set CPU frequency to performance mode


chmod +x automate_scaling.sh

# Define the core counts you want to test sequentially
CORE_STEPS=(1 2 4 8 16 32)

echo "Master script started at: $(date)"
echo "Running configurations: ${CORE_STEPS[*]}"

for CORES in "${CORE_STEPS[@]}"
do
    # Calculate the range (e.g., if CORES is 4, RANGE is "0-3")
    RANGE="0-$((CORES-1))"
    
    echo "=========================================================="
    echo "  BEGINNING TEST: $CORES CORES (Range: $RANGE)"
    echo "=========================================================="
    
    # Run the worker script and WAIT for it to finish (sequential)
    # This ensures energy readings are not contaminated by other runs.
    ./automate_scaling.sh "$CORES" "$RANGE"
    
    echo "  FINISHED $CORES CORES at: $(date)"
    echo "=========================================================="
    echo ""
done

echo "Master script finished all tests at: $(date)"