/* ----------------------------------------------------------------------
   miniMD CHECKPOINT-ONLY VERSION
   
   Modified from original miniMD to SKIP ALL COMPUTATION and only
   perform checkpoint I/O operations. This is for testing checkpoint
   performance in isolation.
   
   Original authors: Steve Plimpton, Paul Crozier, Christian Trott
   Modified by: [Your name] for checkpoint I/O testing
---------------------------------------------------------------------- */

//#define PRINTDEBUG(a) a
#define PRINTDEBUG(a)
#include "stdio.h"
#include "integrate.h"
#include "openmp.h"
#include "math.h"
#include <mpi.h>
#include <iostream>
#include <fstream>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <cerrno>
#include <vector>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
#include <fcntl.h>
#include <dirent.h>

// ========================================================================
// EMBEDDED CHECKPOINT FUNCTIONS (replaces checkpoint.h/checkpoint.cpp)
// ========================================================================

// Clean checkpoint directory on rank 0 (remove old checkpoint files)
// NOTE: Only removes FILES, not the directory itself (preserves symlinks!)
static void clean_checkpoint_dir(const char* dir) {
  int me = 0;
  MPI_Comm_rank(MPI_COMM_WORLD, &me);
  if(me != 0) return;

  if(dir == nullptr || dir[0] == '\0') return;

  struct stat st;
  if(stat(dir, &st) != 0 || !S_ISDIR(st.st_mode)) {
    // Directory doesn't exist, nothing to clean
    return;
  }

  // Open directory (works with symlinks!)
  DIR* dirp = opendir(dir);
  if(dirp == nullptr) {
    std::fprintf(stderr, "WARNING: Could not open checkpoint dir %s for cleanup: %s\n", 
                 dir, std::strerror(errno));
    return;
  }

  // Remove all files in directory (but NOT subdirectories)
  struct dirent* entry;
  int removed_count = 0;
  while((entry = readdir(dirp)) != nullptr) {
    // Skip . and ..
    if(strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0) {
      continue;
    }

    // Build full path
    char filepath[1024];
    snprintf(filepath, sizeof(filepath), "%s/%s", dir, entry->d_name);

    // Check if it's a regular file (not a directory or symlink)
    struct stat file_st;
    if(stat(filepath, &file_st) == 0 && S_ISREG(file_st.st_mode)) {
      // Remove file
      if(unlink(filepath) == 0) {
        removed_count++;
      } else {
        std::fprintf(stderr, "WARNING: Could not remove %s: %s\n", 
                     filepath, std::strerror(errno));
      }
    }
  }

  closedir(dirp);

  if(removed_count > 0) {
    std::printf("Cleaned %d old checkpoint file(s) from %s/\n", removed_count, dir);
  }
}

// Make directory on rank 0 (best-effort)
static void mkdir_rank0(const char* dir) {
  int me = 0;
  MPI_Comm_rank(MPI_COMM_WORLD, &me);
  if(me != 0) return;

  if(dir == nullptr || dir[0] == '\0') return;

  struct stat st;
  if(stat(dir, &st) == 0 && S_ISDIR(st.st_mode)) return;

  if(mkdir(dir, 0755) != 0 && errno != EEXIST) {
    std::fprintf(stderr, "ERROR: mkdir(%s) failed: %s\n", dir, std::strerror(errno));
  }
}

// End-of-simulation checkpoint function that scales with atom count
// Writes actual simulation data (positions, velocities, forces)
static void write_checkpoint_sustained_io(const Atom& atom,
                                          const Comm& comm,
                                          int step,
                                          const char* out_dir,
                                          double target_duration_sec,
                                          size_t chunk_bytes,
                                          int sleep_us,
                                          int fsync_each_chunk)
{
  int me = 0;
  int nprocs = 1;
  MPI_Comm_rank(MPI_COMM_WORLD, &me);
  MPI_Comm_size(MPI_COMM_WORLD, &nprocs);

  const char* dir = (out_dir && out_dir[0]) ? out_dir : "chk";
  
  // Clean old checkpoint files before creating new ones
  clean_checkpoint_dir(dir);
  
  // Ensure directory exists
  mkdir_rank0(dir);

  // Synchronize all ranks before checkpoint (clean I/O phase start)
  MPI_Barrier(MPI_COMM_WORLD);

  double io_start_time = MPI_Wtime();

  char fname[512];
  std::snprintf(fname, sizeof(fname),
                "%s/checkpoint_step%08d_rank%05d.bin",
                dir, step, me);

  // Open file for writing
  int fd = ::open(fname, O_CREAT | O_TRUNC | O_WRONLY, 0644);
  if(fd < 0) {
    std::fprintf(stderr, "ERROR: cannot open %s: %s\n", fname, std::strerror(errno));
    MPI_Barrier(MPI_COMM_WORLD);
    return;
  }

  // === PREPARE ALL DATA FIRST ===
  
  // Header with metadata
  struct CheckpointHeader {
    int32_t nlocal;
    int32_t nghost;
    int32_t ntypes;
    int32_t step;
    int32_t rank;
    int32_t nprocs;
    double box_xlo, box_xhi;
    double box_ylo, box_yhi;
    double box_zlo, box_zhi;
    double box_xprd, box_yprd, box_zprd;
  } header;

  header.nlocal = atom.nlocal;
  header.nghost = atom.nghost;
  header.ntypes = atom.ntypes;
  header.step = step;
  header.rank = me;
  header.nprocs = nprocs;
  header.box_xlo = atom.box.xlo;
  header.box_xhi = atom.box.xhi;
  header.box_ylo = atom.box.ylo;
  header.box_yhi = atom.box.yhi;
  header.box_zlo = atom.box.zlo;
  header.box_zhi = atom.box.zhi;
  header.box_xprd = atom.box.xprd;
  header.box_yprd = atom.box.yprd;
  header.box_zprd = atom.box.zprd;

  // Prepare positions
  std::vector<MMD_float> positions(atom.nlocal * 3);
  for(int i = 0; i < atom.nlocal; i++) {
    positions[i * 3 + 0] = atom.x[i * PAD + 0];
    positions[i * 3 + 1] = atom.x[i * PAD + 1];
    positions[i * 3 + 2] = atom.x[i * PAD + 2];
  }

  // Prepare velocities
  std::vector<MMD_float> velocities(atom.nlocal * 3);
  for(int i = 0; i < atom.nlocal; i++) {
    velocities[i * 3 + 0] = atom.v[i * PAD + 0];
    velocities[i * 3 + 1] = atom.v[i * PAD + 1];
    velocities[i * 3 + 2] = atom.v[i * PAD + 2];
  }

  // Prepare forces
  std::vector<MMD_float> forces(atom.nlocal * 3);
  for(int i = 0; i < atom.nlocal; i++) {
    forces[i * 3 + 0] = atom.f[i * PAD + 0];
    forces[i * 3 + 1] = atom.f[i * PAD + 1];
    forces[i * 3 + 2] = atom.f[i * PAD + 2];
  }

  // Calculate total data size
  size_t total_data_bytes = sizeof(header) +
                            positions.size() * sizeof(MMD_float) +
                            velocities.size() * sizeof(MMD_float) +
                            forces.size() * sizeof(MMD_float);
  
  if(atom.type) {
    total_data_bytes += static_cast<size_t>(atom.nlocal) * sizeof(int);
  }

  // Combine all data into one buffer for chunked writing
  std::vector<unsigned char> all_data;
  all_data.reserve(total_data_bytes);

  // Add header
  const unsigned char* header_ptr = reinterpret_cast<const unsigned char*>(&header);
  all_data.insert(all_data.end(), header_ptr, header_ptr + sizeof(header));

  // Add positions
  const unsigned char* pos_ptr = reinterpret_cast<const unsigned char*>(positions.data());
  all_data.insert(all_data.end(), pos_ptr, pos_ptr + positions.size() * sizeof(MMD_float));

  // Add velocities
  const unsigned char* vel_ptr = reinterpret_cast<const unsigned char*>(velocities.data());
  all_data.insert(all_data.end(), vel_ptr, vel_ptr + velocities.size() * sizeof(MMD_float));

  // Add forces
  const unsigned char* force_ptr = reinterpret_cast<const unsigned char*>(forces.data());
  all_data.insert(all_data.end(), force_ptr, force_ptr + forces.size() * sizeof(MMD_float));

  // Add types
  if(atom.type) {
    const unsigned char* type_ptr = reinterpret_cast<const unsigned char*>(atom.type);
    all_data.insert(all_data.end(), type_ptr, type_ptr + atom.nlocal * sizeof(int));
  }

  // === NOW WRITE DATA IN CHUNKS OVER TARGET DURATION ===
  
  if(chunk_bytes == 0) chunk_bytes = 1024 * 1024; // Default 1 MB chunks
  if(target_duration_sec <= 0.0) target_duration_sec = 30.0; // Default 30 seconds
  
  size_t bytes_written = 0;
  size_t chunk_count = 0;
  double elapsed = 0.0;

  if(me == 0) {
    std::printf("\n=== Starting Sustained I/O Checkpoint ===\n");
    std::printf("Chunk size: %.2f MB\n", chunk_bytes / (1024.0 * 1024.0));
    std::printf("Sleep between chunks: %d microseconds\n", sleep_us);
    std::printf("Data to write per rank: %.2f MB\n", all_data.size() / (1024.0 * 1024.0));
  }

  // Write real checkpoint data AS FAST AS POSSIBLE (no sleep)
  while(bytes_written < all_data.size() && elapsed < target_duration_sec) {
    // Calculate how much to write in this chunk
    size_t bytes_remaining = all_data.size() - bytes_written;
    size_t this_chunk_size = (bytes_remaining < chunk_bytes) ? bytes_remaining : chunk_bytes;

    // Write chunk
    const unsigned char* write_ptr = all_data.data() + bytes_written;
    size_t written_now = 0;
    while(written_now < this_chunk_size) {
      ssize_t result = ::write(fd, write_ptr + written_now, this_chunk_size - written_now);
      if(result < 0) {
        if(errno == EINTR) continue;
        std::fprintf(stderr, "ERROR: write failed on rank %d: %s\n", me, std::strerror(errno));
        ::close(fd);
        MPI_Barrier(MPI_COMM_WORLD);
        return;
      }
      written_now += static_cast<size_t>(result);
    }

    // Optionally fsync each chunk (ensures data hits disk)
    if(fsync_each_chunk) {
      ::fsync(fd);
    }

    bytes_written += this_chunk_size;
    chunk_count++;

    // NO SLEEP for real checkpoint data - write as fast as possible!
    
    elapsed = MPI_Wtime() - io_start_time;
  }

  // If we've written all data but haven't reached target duration,
  // keep writing padding data WITH SLEEP to sustain I/O
  if(elapsed < target_duration_sec && bytes_written >= all_data.size()) {
    if(me == 0) {
      std::printf("All checkpoint data written (%.2f MB in %.2f seconds). Continuing I/O with padding (with sleep) to reach %.1f seconds...\n",
                  bytes_written / (1024.0 * 1024.0), elapsed, target_duration_sec);
    }

    // Create padding buffer (pattern to avoid all zeros)
    std::vector<unsigned char> padding_buf(chunk_bytes);
    for(size_t i = 0; i < padding_buf.size(); i++) {
      padding_buf[i] = static_cast<unsigned char>((i + 173u * static_cast<unsigned>(me)) & 0xFFu);
    }

    while(elapsed < target_duration_sec) {
      // Write padding chunk
      const unsigned char* pad_ptr = padding_buf.data();
      size_t remaining = padding_buf.size();
      while(remaining > 0) {
        ssize_t result = ::write(fd, pad_ptr, remaining);
        if(result < 0) {
          if(errno == EINTR) continue;
          break; // Don't fail on padding write errors
        }
        pad_ptr += static_cast<size_t>(result);
        remaining -= static_cast<size_t>(result);
      }

      if(fsync_each_chunk) {
        ::fsync(fd);
      }

      bytes_written += chunk_bytes;
      chunk_count++;

      if(sleep_us > 0) {
        ::usleep(static_cast<useconds_t>(sleep_us));
      }

      elapsed = MPI_Wtime() - io_start_time;
    }
  }

  // Final fsync and close
  ::fsync(fd);
  ::close(fd);

  double io_end_time = MPI_Wtime();
  double actual_duration = io_end_time - io_start_time;

  // Report statistics on rank 0
  if(me == 0) {
    double total_mb = static_cast<double>(bytes_written) / (1024.0 * 1024.0);
    double data_mb = static_cast<double>(all_data.size()) / (1024.0 * 1024.0);
    double avg_bw = total_mb / actual_duration;
    
    std::printf("\n=== I/O Checkpoint Complete ===\n");
    std::printf("Actual I/O duration: %.2f seconds\n", actual_duration);
    std::printf("Checkpoint data written: %.2f MB per rank\n", data_mb);
    std::printf("Total written (with padding): %.2f MB per rank\n", total_mb);
    std::printf("Number of chunks: %zu\n", chunk_count);
    std::printf("Average bandwidth: %.2f MB/s per rank\n", avg_bw);
    std::printf("=====================================\n\n");
  }

  // Synchronize all ranks after checkpoint (clean I/O phase end)
  MPI_Barrier(MPI_COMM_WORLD);

  // Prevent unused warning
  (void)comm;
}

// ========================================================================
// END OF EMBEDDED CHECKPOINT FUNCTIONS
// ========================================================================

Integrate::Integrate() {
  sort_every=20;
  
  // Checkpoint defaults
  ckpt_interval = 0;     // disabled unless user sets --ckpt
  ckpt_dir = "chk";      // default output directory
  ckpt_at_end = 1;       // Enable end-of-simulation checkpoint by default

  // Sustained I/O defaults (for monitoring I/O effects)
  ckpt_io_duration_sec = 30.0;
  ckpt_chunk_bytes = 1024 * 1024;
  ckpt_sleep_us = 100000; // 100 ms
  ckpt_fsync_chunks = 0;
}

Integrate::~Integrate() {}

void Integrate::setup()
{
  dtforce = 0.5 * dt;
}

void Integrate::initialIntegrate()
{
  // CHECKPOINT-ONLY MODE: Skip computation
  // Original code commented out:
  /*
  OMPFORSCHEDULE
  for(MMD_int i = 0; i < nlocal; i++) {
    v[i * PAD + 0] += dtforce * f[i * PAD + 0];
    v[i * PAD + 1] += dtforce * f[i * PAD + 1];
    v[i * PAD + 2] += dtforce * f[i * PAD + 2];
    x[i * PAD + 0] += dt * v[i * PAD + 0];
    x[i * PAD + 1] += dt * v[i * PAD + 1];
    x[i * PAD + 2] += dt * v[i * PAD + 2];
  }
  */
}

void Integrate::finalIntegrate()
{
  // CHECKPOINT-ONLY MODE: Skip computation
  // Original code commented out:
  /*
  OMPFORSCHEDULE
  for(MMD_int i = 0; i < nlocal; i++) {
    v[i * PAD + 0] += dtforce * f[i * PAD + 0];
    v[i * PAD + 1] += dtforce * f[i * PAD + 1];
    v[i * PAD + 2] += dtforce * f[i * PAD + 2];
  }
  */
}

void Integrate::run(Atom &atom, Force* force, Neighbor &neighbor,
                    Comm &comm, Thermo &thermo, Timer &timer)
{
  int i, n;
  int me = 0;
  MPI_Comm_rank(MPI_COMM_WORLD, &me);

  comm.timer = &timer;
  timer.array[TIME_TEST] = 0.0;

  int check_safeexchange = comm.check_safeexchange;

  mass = atom.mass;
  dtforce = dtforce / mass;
  
  // ========================================================================
  // CHECKPOINT-ONLY MODE
  // Skip all timestep iterations and go straight to checkpoint
  // ========================================================================
  
  if(me == 0) {
    std::printf("\n========================================\n");
    std::printf("CHECKPOINT-ONLY MODE\n");
    std::printf("Skipping all MD computation\n");
    std::printf("Going directly to checkpoint I/O\n");
    std::printf("========================================\n");
  }
  
  // Use step 0 since we're checkpointing initial state (not mid-simulation)
  int checkpoint_step = 0;
  
  // Small delay to simulate some initial work
  if(me == 0) {
    std::printf("\nSimulating minimal initialization...\n");
  }
  sleep(2);
  
  // -------------------------------------------------------
  // CHECKPOINT I/O (the only thing we actually do)
  // -------------------------------------------------------
  
  if(me == 0) {
    std::printf("\n========================================\n");
    std::printf("Performing checkpoint with sustained I/O\n");
    std::printf("Target duration: %.1f seconds\n", ckpt_io_duration_sec);
    std::printf("Chunk size: %.2f MB\n", ckpt_chunk_bytes / (1024.0 * 1024.0));
    std::printf("Sleep between chunks: %d ms\n", ckpt_sleep_us / 1000);
    std::printf("========================================\n");
  }
  
  // Perform the checkpoint
  timer.barrier_start(TIME_TOTAL);
  
  write_checkpoint_sustained_io(atom, comm, checkpoint_step, ckpt_dir,
                                ckpt_io_duration_sec,
                                ckpt_chunk_bytes,
                                ckpt_sleep_us,
                                ckpt_fsync_chunks);
  
  timer.barrier_stop(TIME_TOTAL);
  
  if(me == 0) {
    std::printf("\n========================================\n");
    std::printf("CHECKPOINT-ONLY MODE COMPLETE\n");
    std::printf("All computation was skipped\n");
    std::printf("Only checkpoint I/O was performed\n");
    std::printf("========================================\n");
  }
  
  // Update timer with fake values for compatibility
  timer.array[TIME_FORCE] = 0.0;
  timer.array[TIME_NEIGH] = 0.0;
  timer.array[TIME_COMM] = 0.0;
  
  // Prevent unused variable warnings
  (void)force;
  (void)neighbor;
  (void)thermo;
  (void)check_safeexchange;
  (void)i;
  (void)n;
}
