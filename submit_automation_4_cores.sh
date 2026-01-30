#!/bin/bash
#SBATCH --job-name=miniMD_energy      # Name of your job
#SBATCH --output=4_cores_batch_result_%j.out        # Output file (%j expands to JobID)
#SBATCH --nodes=1                     # Request 1 physical node
#SBATCH --ntasks=4                    # Total number of MPI tasks
#SBATCH --cpus-per-task=1             # Cores per task
#SBATCH --time=18:00:00               # Max runtime (HH:MM:SS)
#SBATCH --mem=8G
#SBATCH --exclusive
#SBATCH --cpu-freq=performance        # Set CPU frequency to performance mode
#SBATCH --partition=gpu-rgrant          # Name of the queue
#SBATCH --mail-user=20wyvs@queensu.ca
#SBATCH --mail-type=END,FAIL

export EXEC_WRAPPER="numactl --localalloc"

export OMP_NUM_THREADS=1
export OMP_PROC_BIND=true           # Changed to true to prevent migrations
export OMP_PLACES=cores             # Pins the thread to a specific core

# Run the automation script
chmod +x automate_baseline_4_cores.sh
./automate_baseline_4_cores.sh