#include "atom.h"
#include "force.h"
#include "neighbor.h"
#include "comm.h"
#include "thermo.h"
#include "timer.h"
#include "threadData.h"

#include <cstddef>

class Integrate
{
  public:
    MMD_float dt;
    MMD_float dtforce;
    MMD_int ntimes;
    MMD_int nlocal, nmax;
    MMD_float* x, *v, *f, *xold;
    MMD_float mass;

    MMD_int sort_every;

    // Checkpoint configuration (I/O scaling only)
    MMD_int ckpt_interval;          // Checkpoint every N timesteps (0 = disabled)
    const char* ckpt_dir;           // Output directory for checkpoint files

    // I/O scaling parameters (for 30-second sustained I/O)
    double ckpt_ioscale_sec;        // Duration to write (seconds) - default 30.0
    size_t ckpt_ioscale_chunk_bytes;// Bytes per chunk write - default 1MB
    int ckpt_ioscale_sleep_us;      // Sleep between chunks (microseconds) - default 100ms

    Integrate();
    ~Integrate();
    void setup();
    void initialIntegrate();
    void finalIntegrate();
    void run(Atom &, Force*, Neighbor &, Comm &, Thermo &, Timer &);

    ThreadData* threads;
};
