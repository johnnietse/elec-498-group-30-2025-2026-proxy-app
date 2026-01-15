#!/bin/bash
#SBATCH --job-name=miniMD_energy      # Name of your job
#SBATCH --output=32_cores_batch_result_%j.out        # Output file (%j expands to JobID)
#SBATCH --nodes=1                     # Request 1 physical node
#SBATCH --ntasks=32                    # Total number of MPI tasks
#SBATCH --cpus-per-task=1             # Cores per task
#SBATCH --time=18:00:00               # Max runtime (HH:MM:SS)
#SBATCH --mem=8G
#SBATCH --partition=gpu-rgrant          # Name of the queue (check your cluster docs)
#SBATCH --mail-user=20wyvs@queensu.ca
#SBATCH --mail-type=END,FAIL

# Run the automation script
chmod +x automate_baseline_32_cores.sh
./automate_baseline_32_cores.sh