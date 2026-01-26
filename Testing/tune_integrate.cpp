/* ----------------------------------------------------------------------
   miniMD is a simple, parallel molecular dynamics (MD) code.
---------------------------------------------------------------------- */
//#define PRINTDEBUG(a) a
#define PRINTDEBUG(a)
#include "stdio.h"
#include "integrate.h"
#include "openmp.h"
#include "math.h"
#include <mpi.h> 
#include <sys/time.h> // [FIX] Needed for Unix Epoch timestamps

// --- [INSTRUMENTATION] Global File Handle for Ground Truth ---
static FILE* truth_log = NULL;

// [FIX] Helper to get time matching Python's time.time()
double get_epoch_time() {
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return tv.tv_sec + (tv.tv_usec / 1000000.0);
}

Integrate::Integrate() {sort_every=20;}
Integrate::~Integrate() {
    if (truth_log) fclose(truth_log);
}

void Integrate::setup()
{
  dtforce = 0.5 * dt;
}

void Integrate::initialIntegrate()
{
  OMPFORSCHEDULE
  for(MMD_int i = 0; i < nlocal; i++) {
    v[i * PAD + 0] += dtforce * f[i * PAD + 0];
    v[i * PAD + 1] += dtforce * f[i * PAD + 1];
    v[i * PAD + 2] += dtforce * f[i * PAD + 2];
    x[i * PAD + 0] += dt * v[i * PAD + 0];
    x[i * PAD + 1] += dt * v[i * PAD + 1];
    x[i * PAD + 2] += dt * v[i * PAD + 2];
  }
}

void Integrate::finalIntegrate()
{
  OMPFORSCHEDULE
  for(MMD_int i = 0; i < nlocal; i++) {
    v[i * PAD + 0] += dtforce * f[i * PAD + 0];
    v[i * PAD + 1] += dtforce * f[i * PAD + 1];
    v[i * PAD + 2] += dtforce * f[i * PAD + 2];
  }
}

void Integrate::run(Atom &atom, Force* force, Neighbor &neighbor,
                    Comm &comm, Thermo &thermo, Timer &timer)
{
  int i, n;

  comm.timer = &timer;
  timer.array[TIME_TEST] = 0.0;

  int check_safeexchange = comm.check_safeexchange;

  mass = atom.mass;
  dtforce = dtforce / mass;

  // --- [INSTRUMENTATION] Initialize Log File ---
  if (truth_log == NULL) {
      int rank;
      MPI_Comm_rank(MPI_COMM_WORLD, &rank);
      
      // ONLY Rank 0 should write the log to avoid file locking issues
      // logic: assuming all ranks are roughly in sync phase-wise
      if (rank == 0) {
          truth_log = fopen("ground_truth.csv", "w");
          // [FIX] Header matches Python script expectations
          if (truth_log) fprintf(truth_log, "timestamp,actual_phase\n");
      }
  }

  #pragma omp parallel private(i,n)
  {
    int next_sort = sort_every>0?sort_every:ntimes+1;

    for(n = 0; n < ntimes; n++) {

      #pragma omp barrier

      x = atom.x;
      v = atom.v;
      f = atom.f;
      xold = atom.xold;
      nlocal = atom.nlocal;

      initialIntegrate();

      #pragma omp master
      timer.stamp();

      if((n + 1) % neighbor.every) {

        // --- [INSTRUMENTATION] Start COMM ---
        #pragma omp master
        if(truth_log) fprintf(truth_log, "%.6f,COMMUNICATION\n", get_epoch_time());

        comm.communicate(atom);
        
        // Note: We don't need to log "END" because the next "START" 
        // will implicitly mark the transition for the Python merger.

        #pragma omp master
        timer.stamp(TIME_COMM);

      } else {
        // --- [INSTRUMENTATION] Start COMM (Reneighbor) ---
        #pragma omp master
        if(truth_log) fprintf(truth_log, "%.6f,COMMUNICATION\n", get_epoch_time());

        {
          if(check_safeexchange) {
            #pragma omp master
            {
              double d_max = 0;
              for(i = 0; i < atom.nlocal; i++) {
                double dx = (x[i * PAD + 0] - xold[i * PAD + 0]);
                if(dx > atom.box.xprd) dx -= atom.box.xprd;
                if(dx < -atom.box.xprd) dx += atom.box.xprd;
                double dy = (x[i * PAD + 1] - xold[i * PAD + 1]);
                if(dy > atom.box.yprd) dy -= atom.box.yprd;
                if(dy < -atom.box.yprd) dy += atom.box.yprd;
                double dz = (x[i * PAD + 2] - xold[i * PAD + 2]);
                if(dz > atom.box.zprd) dz -= atom.box.zprd;
                if(dz < -atom.box.zprd) dz += atom.box.zprd;
                double d = dx * dx + dy * dy + dz * dz;
                if(d > d_max) d_max = d;
              }
              d_max = sqrt(d_max);
              if((d_max > atom.box.xhi - atom.box.xlo) || (d_max > atom.box.yhi - atom.box.ylo) || (d_max > atom.box.zhi - atom.box.zlo))
                printf("Warning: Atoms move further than your subdomain size...\n");
            }
          }

          #pragma omp master
          timer.stamp_extra_start();
          
          comm.exchange(atom);
          
          if(n+1>=next_sort) {
            atom.sort(neighbor);
            next_sort +=  sort_every;
          }
          
          comm.borders(atom);
          
          #pragma omp master
          {
            timer.stamp_extra_stop(TIME_TEST);
            timer.stamp(TIME_COMM);
          }

          if(check_safeexchange)
            for(int i = 0; i < PAD * atom.nlocal; i++) xold[i] = x[i];
        }

        #pragma omp barrier

        // --- [INSTRUMENTATION] Start MEMORY ---
        #pragma omp master
        if(truth_log) fprintf(truth_log, "%.6f,MEMORY_BOUND\n", get_epoch_time());

        neighbor.build(atom);

        #pragma omp master
        timer.stamp(TIME_NEIGH);
      }

      force->evflag = (n + 1) % thermo.nstat == 0;

      // --- [INSTRUMENTATION] Start COMPUTE ---
      #pragma omp master
      if(truth_log) fprintf(truth_log, "%.6f,COMPUTE\n", get_epoch_time());

      force->compute(atom, neighbor, comm, comm.me);

      #pragma omp master
      timer.stamp(TIME_FORCE);

      if(neighbor.halfneigh && neighbor.ghost_newton) {
        
        // --- [INSTRUMENTATION] Start COMM (Reverse) ---
        #pragma omp master
        if(truth_log) fprintf(truth_log, "%.6f,COMMUNICATION\n", get_epoch_time());

        comm.reverse_communicate(atom);

        #pragma omp master
        timer.stamp(TIME_COMM);
      }

      v = atom.v;
      f = atom.f;
      nlocal = atom.nlocal;

      #pragma omp barrier

      finalIntegrate();

      if(thermo.nstat) thermo.compute(n + 1, atom, neighbor, force, timer, comm);
    }
  } //end OpenMP parallel
}