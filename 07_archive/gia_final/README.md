# elec-498-group-30-2025-2026-proxy-app

1. commands for running ...
     1.1 salloc properly
     salloc --nodes=1 --partition=gpu-rgrant --constraint=lkb --ntasks=16 --cpus-per-task=1

     1.2 delete chk directory to delete old checkpoints (optional) 
         rm chk

     1.2 mpirun 
      mpirun --oversubscribe -np 16 \
        ./miniMD_openmpi \
        -i in.lj.miniMD \
        --ckpt 200 \ (checkpoint at timestep 200) 

3. run monitoring script
   
4. Checking Checkpoints XD
     1.1 cd chk
     1.2 ls

      * should see a bunch of checkpoints listed (each rank does one checkpoint at each timestep)

     1.3 get the raw binary throughput 
       $ hexdump -C chk_step00002900_rank00002.bin | head (chk_step00002900_rank00002.bin is just an example)

     1.4 go back to ref directory and find the file size.
         cd ..
         ls -lh chk/ | grep ioscale (should be 300MB which checks out in light load but drops in higher loads)
                                    (cuz 10MB/s x 30 seconds with 0.1s sleep time)

   
