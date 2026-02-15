# elec-498-group-30-2025-2026-proxy-app

Read Me for Jhonnie

1. copy integrate.cpp, integrate.h, ljs.cpp
2. make opempi -j 8
3. Have only one core running 
     salloc --nodes=1 --partition=gpu-rgrant --constraint=lkb --ntasks=1 --cpus-per-task=1
   
5. cd /home/hpc6084/frnt115/minimd/ref

6. link chk directory
     echo $SLURM_TMPDIR
     df -h /lscratch/slurm-job-2490120-1  **change the job number to whatever your job number is**
     ln -s $SLURM_TMPDIR/chk chk
     ls -l chk **Should show: chk -> /lscratch/slurm-job-2497329-1/chk**

7. set in.lj.miniMD to desired load.

8. run mpi
     mpirun --oversubscribe -np 1   ./miniMD_openmpi   -i in.lj.miniMD

9. check the directories 
    ls -lh  /lscratch/slurm-job-2497336-1/chk
    du -sh /lscratch/slurm-job-2497336-1/chk

10. remove all files for the next run.
     rm -rf chk




     
   



