/* ----------------------------------------------------------------------
   miniMD is a simple, parallel molecular dynamics (MD) code.   miniMD is
   an MD microapplication in the Mantevo project at Sandia National
   Laboratories ( http://www.mantevo.org ). The primary
   authors of miniMD are Steve Plimpton (sjplimp@sandia.gov) , Paul Crozier
   (pscrozi@sandia.gov) and Christian Trott (crtrott@sandia.gov).

   Copyright (2008) Sandia Corporation.  Under the terms of Contract
   DE-AC04-94AL85000 with Sandia Corporation, the U.S. Government retains
   certain rights in this software.  This library is free software; you
   can redistribute it and/or modify it under the terms of the GNU Lesser
   General Public License as published by the Free Software Foundation;
   either version 3 of the License, or (at your option) any later
   version.

   This library is distributed in the hope that it will be useful, but
   WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
   Lesser General Public License for more details.

   You should have received a copy of the GNU Lesser General Public
   License along with this software; if not, write to the Free Software
   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
   USA.  See also: http://www.gnu.org/licenses/lgpl.txt .

   For questions, contact Paul S. Crozier (pscrozi@sandia.gov) or
   Christian Trott (crtrott@sandia.gov).

   Please read the accompanying README and LICENSE files.
---------------------------------------------------------------------- */
// #define PRINTDEBUG(a) a
#define PRINTDEBUG(a)
#include "integrate.h"
#include "math.h"
#include "openmp.h"
#include "stdio.h"
#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <dirent.h>
#include <fcntl.h>
#include <fstream>
#include <iostream>
#include <mpi.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
#include <vector>


// ========================================================================
// EMBEDDED CHECKPOINT FUNCTIONS (from Gia's I/O phase code)
// ========================================================================

// Clean checkpoint directory on rank 0 (remove old checkpoint files)
// NOTE: Only removes FILES, not the directory itself (preserves symlinks!)
static void clean_checkpoint_dir(const char *dir) {
  int me = 0;
  MPI_Comm_rank(MPI_COMM_WORLD, &me);
  if (me != 0)
    return;

  if (dir == nullptr || dir[0] == '\0')
    return;

  struct stat st;
  if (stat(dir, &st) != 0 || !S_ISDIR(st.st_mode)) {
    return;
  }

  DIR *dirp = opendir(dir);
  if (dirp == nullptr) {
    std::fprintf(stderr,
                 "WARNING: Could not open checkpoint dir %s for cleanup: %s\n",
                 dir, std::strerror(errno));
    return;
  }

  struct dirent *entry;
  int removed_count = 0;
  while ((entry = readdir(dirp)) != nullptr) {
    if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0) {
      continue;
    }

    char filepath[1024];
    snprintf(filepath, sizeof(filepath), "%s/%s", dir, entry->d_name);

    struct stat file_st;
    if (stat(filepath, &file_st) == 0 && S_ISREG(file_st.st_mode)) {
      if (unlink(filepath) == 0) {
        removed_count++;
      } else {
        std::fprintf(stderr, "WARNING: Could not remove %s: %s\n", filepath,
                     std::strerror(errno));
      }
    }
  }

  closedir(dirp);

  if (removed_count > 0) {
    std::printf("Cleaned %d old checkpoint file(s) from %s/\n", removed_count,
                dir);
  }
}

// Make directory on rank 0 (best-effort)
static void mkdir_rank0(const char *dir) {
  int me = 0;
  MPI_Comm_rank(MPI_COMM_WORLD, &me);
  if (me != 0)
    return;

  if (dir == nullptr || dir[0] == '\0')
    return;

  struct stat st;
  if (stat(dir, &st) == 0 && S_ISDIR(st.st_mode))
    return;

  if (mkdir(dir, 0755) != 0 && errno != EEXIST) {
    std::fprintf(stderr, "ERROR: mkdir(%s) failed: %s\n", dir,
                 std::strerror(errno));
  }
}

// End-of-simulation checkpoint function that scales with atom count
// Writes actual simulation data (positions, velocities, forces)
static void write_checkpoint_sustained_io(const Atom &atom, const Comm &comm,
                                          int step, const char *out_dir,
                                          double target_duration_sec,
                                          size_t chunk_bytes, int sleep_us,
                                          int fsync_each_chunk) {
  int me = 0;
  int nprocs = 1;
  MPI_Comm_rank(MPI_COMM_WORLD, &me);
  MPI_Comm_size(MPI_COMM_WORLD, &nprocs);

  const char *dir = (out_dir && out_dir[0]) ? out_dir : "chk";

  clean_checkpoint_dir(dir);
  mkdir_rank0(dir);

  MPI_Barrier(MPI_COMM_WORLD);

  double io_start_time = MPI_Wtime();

  char fname[512];
  std::snprintf(fname, sizeof(fname), "%s/checkpoint_step%08d_rank%05d.bin",
                dir, step, me);

  int fd = ::open(fname, O_CREAT | O_TRUNC | O_WRONLY, 0644);
  if (fd < 0) {
    std::fprintf(stderr, "ERROR: cannot open %s: %s\n", fname,
                 std::strerror(errno));
    MPI_Barrier(MPI_COMM_WORLD);
    return;
  }

  // === PREPARE ALL DATA FIRST ===

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

  std::vector<MMD_float> positions(atom.nlocal * 3);
  for (int i = 0; i < atom.nlocal; i++) {
    positions[i * 3 + 0] = atom.x[i * PAD + 0];
    positions[i * 3 + 1] = atom.x[i * PAD + 1];
    positions[i * 3 + 2] = atom.x[i * PAD + 2];
  }

  std::vector<MMD_float> velocities(atom.nlocal * 3);
  for (int i = 0; i < atom.nlocal; i++) {
    velocities[i * 3 + 0] = atom.v[i * PAD + 0];
    velocities[i * 3 + 1] = atom.v[i * PAD + 1];
    velocities[i * 3 + 2] = atom.v[i * PAD + 2];
  }

  std::vector<MMD_float> forces(atom.nlocal * 3);
  for (int i = 0; i < atom.nlocal; i++) {
    forces[i * 3 + 0] = atom.f[i * PAD + 0];
    forces[i * 3 + 1] = atom.f[i * PAD + 1];
    forces[i * 3 + 2] = atom.f[i * PAD + 2];
  }

  size_t total_data_bytes =
      sizeof(header) + positions.size() * sizeof(MMD_float) +
      velocities.size() * sizeof(MMD_float) + forces.size() * sizeof(MMD_float);

  if (atom.type) {
    total_data_bytes += static_cast<size_t>(atom.nlocal) * sizeof(int);
  }

  std::vector<unsigned char> all_data;
  all_data.reserve(total_data_bytes);

  const unsigned char *header_ptr =
      reinterpret_cast<const unsigned char *>(&header);
  all_data.insert(all_data.end(), header_ptr, header_ptr + sizeof(header));

  const unsigned char *pos_ptr =
      reinterpret_cast<const unsigned char *>(positions.data());
  all_data.insert(all_data.end(), pos_ptr,
                  pos_ptr + positions.size() * sizeof(MMD_float));

  const unsigned char *vel_ptr =
      reinterpret_cast<const unsigned char *>(velocities.data());
  all_data.insert(all_data.end(), vel_ptr,
                  vel_ptr + velocities.size() * sizeof(MMD_float));

  const unsigned char *force_ptr =
      reinterpret_cast<const unsigned char *>(forces.data());
  all_data.insert(all_data.end(), force_ptr,
                  force_ptr + forces.size() * sizeof(MMD_float));

  if (atom.type) {
    const unsigned char *type_ptr =
        reinterpret_cast<const unsigned char *>(atom.type);
    all_data.insert(all_data.end(), type_ptr,
                    type_ptr + atom.nlocal * sizeof(int));
  }

  // === NOW WRITE DATA IN CHUNKS OVER TARGET DURATION ===

  if (chunk_bytes == 0)
    chunk_bytes = 1024 * 1024;
  if (target_duration_sec <= 0.0)
    target_duration_sec = 30.0;

  size_t bytes_written = 0;
  size_t chunk_count = 0;
  double elapsed = 0.0;

  if (me == 0) {
    std::printf("\n=== Starting Sustained I/O Checkpoint ===\n");
    std::printf("Chunk size: %.2f MB\n", chunk_bytes / (1024.0 * 1024.0));
    std::printf("Sleep between chunks: %d microseconds\n", sleep_us);
    std::printf("Data to write per rank: %.2f MB\n",
                all_data.size() / (1024.0 * 1024.0));
  }

  // Write real checkpoint data AS FAST AS POSSIBLE (no sleep)
  while (bytes_written < all_data.size() && elapsed < target_duration_sec) {
    size_t bytes_remaining = all_data.size() - bytes_written;
    size_t this_chunk_size =
        (bytes_remaining < chunk_bytes) ? bytes_remaining : chunk_bytes;

    const unsigned char *write_ptr = all_data.data() + bytes_written;
    size_t written_now = 0;
    while (written_now < this_chunk_size) {
      ssize_t result =
          ::write(fd, write_ptr + written_now, this_chunk_size - written_now);
      if (result < 0) {
        if (errno == EINTR)
          continue;
        std::fprintf(stderr, "ERROR: write failed on rank %d: %s\n", me,
                     std::strerror(errno));
        ::close(fd);
        MPI_Barrier(MPI_COMM_WORLD);
        return;
      }
      written_now += static_cast<size_t>(result);
    }

    if (fsync_each_chunk) {
      ::fsync(fd);
    }

    bytes_written += this_chunk_size;
    chunk_count++;

    elapsed = MPI_Wtime() - io_start_time;
  }

  // If we've written all data but haven't reached target duration,
  // keep writing padding data WITH SLEEP to sustain I/O
  if (elapsed < target_duration_sec && bytes_written >= all_data.size()) {
    if (me == 0) {
      std::printf("All checkpoint data written (%.2f MB in %.2f seconds). "
                  "Continuing I/O with padding to reach %.1f seconds...\n",
                  bytes_written / (1024.0 * 1024.0), elapsed,
                  target_duration_sec);
    }

    std::vector<unsigned char> padding_buf(chunk_bytes);
    for (size_t i = 0; i < padding_buf.size(); i++) {
      padding_buf[i] = static_cast<unsigned char>(
          (i + 173u * static_cast<unsigned>(me)) & 0xFFu);
    }

    while (elapsed < target_duration_sec) {
      const unsigned char *pad_ptr = padding_buf.data();
      size_t remaining = padding_buf.size();
      while (remaining > 0) {
        ssize_t result = ::write(fd, pad_ptr, remaining);
        if (result < 0) {
          if (errno == EINTR)
            continue;
          break;
        }
        pad_ptr += static_cast<size_t>(result);
        remaining -= static_cast<size_t>(result);
      }

      if (fsync_each_chunk) {
        ::fsync(fd);
      }

      bytes_written += chunk_bytes;
      chunk_count++;

      if (sleep_us > 0) {
        ::usleep(static_cast<useconds_t>(sleep_us));
      }

      elapsed = MPI_Wtime() - io_start_time;
    }
  }

  ::fsync(fd);
  ::close(fd);

  double io_end_time = MPI_Wtime();
  double actual_duration = io_end_time - io_start_time;

  if (me == 0) {
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

  MPI_Barrier(MPI_COMM_WORLD);

  (void)comm;
}

// ========================================================================
// END OF EMBEDDED CHECKPOINT FUNCTIONS
// ========================================================================

// ========================================================================
// COMMUNICATION PHASE (Johnnie)
// Simulates network communication by sending checkpoint-equivalent data
// through MPI on rank 0 only. Other ranks wait at MPI_Barrier.
//
// Design rationale (per Dr. Grant's guidance):
//   - Only 1 MPI rank handles all network I/O
//   - Use MPI_Send/MPI_Recv loopback (rank 0 -> rank 0)
//   - The payload size = per-rank checkpoint bytes × nprocs
//   - This consolidates N separate network operations into 1
//   - Other ranks are idle → their cores can run at low frequency
// ========================================================================

// Calculate the per-rank checkpoint data size from atom data
// Formula: header (96 bytes) + nlocal * 3 * sizeof(MMD_float) * 3
// [pos+vel+force]
//          + nlocal * sizeof(int) [types]
static size_t calculate_per_rank_data_bytes(const Atom &atom) {
  // Header: 6 int32_t + 9 doubles = 24 + 72 = 96 bytes
  size_t header_bytes = 6 * sizeof(int32_t) + 9 * sizeof(double);

  // Positions: nlocal * 3 * sizeof(MMD_float)
  // Velocities: nlocal * 3 * sizeof(MMD_float)
  // Forces: nlocal * 3 * sizeof(MMD_float)
  size_t array_bytes =
      static_cast<size_t>(atom.nlocal) * 3 * sizeof(MMD_float) * 3;

  // Types: nlocal * sizeof(int)
  size_t type_bytes = 0;
  if (atom.type) {
    type_bytes = static_cast<size_t>(atom.nlocal) * sizeof(int);
  }

  return header_bytes + array_bytes + type_bytes;
}

static void simulate_network_communication(const Atom &atom, int nprocs,
                                           size_t standin_total_bytes,
                                           size_t chunk_kb) {
  int me = 0;
  MPI_Comm_rank(MPI_COMM_WORLD, &me);

  // ---- Calculate actual data size from atom.nlocal ----
  size_t per_rank_bytes = calculate_per_rank_data_bytes(atom);
  size_t runtime_total_bytes = per_rank_bytes * static_cast<size_t>(nprocs);

  // Use the larger of: runtime calculation vs stand-in (309 MB)
  // This ensures we transfer at least the expected amount
  size_t total_bytes = runtime_total_bytes;

  if (me == 0) {
    std::printf("\n========================================\n");
    std::printf("COMMUNICATION PHASE (Rank 0 Only)\n");
    std::printf("========================================\n");
    std::printf("Per-rank data (runtime): %.2f MB (%zu bytes)\n",
                per_rank_bytes / (1024.0 * 1024.0), per_rank_bytes);
    std::printf(
        "Total data (runtime): %.2f MB (%zu bytes) [%d ranks × per-rank]\n",
        runtime_total_bytes / (1024.0 * 1024.0), runtime_total_bytes, nprocs);
    std::printf("Stand-in total: %.2f MB (%zu bytes)\n",
                standin_total_bytes / (1024.0 * 1024.0), standin_total_bytes);

    if (runtime_total_bytes < standin_total_bytes) {
      std::printf("NOTE: Runtime total (%.2f MB) < stand-in (%.2f MB). Using "
                  "stand-in.\n",
                  runtime_total_bytes / (1024.0 * 1024.0),
                  standin_total_bytes / (1024.0 * 1024.0));
      total_bytes = standin_total_bytes;
    } else {
      std::printf("Using runtime total: %.2f MB\n",
                  total_bytes / (1024.0 * 1024.0));
    }
  }

  // Broadcast the total_bytes decision from rank 0
  MPI_Bcast(&total_bytes, sizeof(size_t), MPI_BYTE, 0, MPI_COMM_WORLD);

  // Signal communication start to Python monitor
  if (me == 0) {
    FILE *fp = std::fopen("phase_marker.txt", "w");
    if (fp) {
      std::fprintf(fp, "COMM_START %zu\n", total_bytes);
      std::fclose(fp);
    }
  }

  // ---- All ranks synchronize before communication ----
  MPI_Barrier(MPI_COMM_WORLD);

  double comm_start = MPI_Wtime();

  // ---- Only rank 0 does the actual network send/recv (loopback) ----
  if (me == 0) {
    size_t chunk_bytes = chunk_kb * 1024;
    if (chunk_bytes == 0)
      chunk_bytes = 1024 * 1024; // default 1 MB

    // Allocate send and receive buffers
    // For very large transfers, do it in chunks to avoid OOM
    size_t buf_size = (chunk_bytes < total_bytes) ? chunk_bytes : total_bytes;
    std::vector<char> send_buf(buf_size);
    std::vector<char> recv_buf(buf_size);

    // Fill send buffer with a pattern (not all zeros)
    for (size_t i = 0; i < buf_size; i++) {
      send_buf[i] = static_cast<char>((i * 7 + 13) & 0xFF);
    }

    size_t bytes_sent = 0;
    size_t chunk_count = 0;

    std::printf("Starting MPI loopback send/recv (rank 0 -> rank 0)\n");
    std::printf("Total bytes to transfer: %.2f MB\n",
                total_bytes / (1024.0 * 1024.0));
    std::printf("Chunk size: %.2f KB\n", buf_size / 1024.0);

    while (bytes_sent < total_bytes) {
      size_t remaining = total_bytes - bytes_sent;
      int this_chunk =
          static_cast<int>((remaining < buf_size) ? remaining : buf_size);

      // MPI loopback: rank 0 sends to rank 0
      // Use non-blocking send + blocking recv to avoid deadlock
      MPI_Request send_req;
      MPI_Isend(send_buf.data(), this_chunk, MPI_BYTE, 0, 99, MPI_COMM_WORLD,
                &send_req);
      MPI_Recv(recv_buf.data(), this_chunk, MPI_BYTE, 0, 99, MPI_COMM_WORLD,
               MPI_STATUS_IGNORE);
      MPI_Wait(&send_req, MPI_STATUS_IGNORE);

      bytes_sent += static_cast<size_t>(this_chunk);
      chunk_count++;

      // Progress report every 50 MB
      if (chunk_count % (50 * 1024 * 1024 / (int)buf_size + 1) == 0) {
        std::printf("  ... sent %.2f / %.2f MB\n",
                    bytes_sent / (1024.0 * 1024.0),
                    total_bytes / (1024.0 * 1024.0));
      }
    }

    std::printf("MPI loopback complete: %zu chunks, %.2f MB total\n",
                chunk_count, bytes_sent / (1024.0 * 1024.0));
  }

  // ---- All ranks synchronize after communication ----
  MPI_Barrier(MPI_COMM_WORLD);

  double comm_end = MPI_Wtime();
  double comm_duration = comm_end - comm_start;

  // Signal communication end to Python monitor
  if (me == 0) {
    FILE *fp = std::fopen("phase_marker.txt", "w");
    if (fp) {
      std::fprintf(fp, "COMM_END\n");
      std::fclose(fp);
    }

    std::printf("\n=== Communication Phase Complete ===\n");
    std::printf("Duration: %.3f seconds\n", comm_duration);
    std::printf("Effective bandwidth: %.2f MB/s\n",
                total_bytes / (1024.0 * 1024.0) / comm_duration);
    std::printf("====================================\n\n");
  }
}

// ========================================================================
// END OF COMMUNICATION PHASE
// ========================================================================

Integrate::Integrate() {
  sort_every = 20;

  // Checkpoint defaults (Gia's I/O phase)
  ckpt_interval = 0;
  ckpt_dir = "chk";
  ckpt_at_end = 1;

  ckpt_io_duration_sec = 30.0;
  ckpt_chunk_bytes = 1024 * 1024;
  ckpt_sleep_us = 100000; // 100 ms
  ckpt_fsync_chunks = 0;

  // Communication phase defaults (Johnnie)
  comm_phase_enabled = 1;                         // enabled by default
  comm_standin_bytes = (size_t)309 * 1024 * 1024; // 309 MB stand-in
  comm_chunk_kb = 1024; // 1 MB chunks for MPI send/recv
}

Integrate::~Integrate() {}

void Integrate::setup() { dtforce = 0.5 * dt; }

void Integrate::initialIntegrate() {
  OMPFORSCHEDULE
  for (MMD_int i = 0; i < nlocal; i++) {
    v[i * PAD + 0] += dtforce * f[i * PAD + 0];
    v[i * PAD + 1] += dtforce * f[i * PAD + 1];
    v[i * PAD + 2] += dtforce * f[i * PAD + 2];
    x[i * PAD + 0] += dt * v[i * PAD + 0];
    x[i * PAD + 1] += dt * v[i * PAD + 1];
    x[i * PAD + 2] += dt * v[i * PAD + 2];
  }
}

void Integrate::finalIntegrate() {
  OMPFORSCHEDULE
  for (MMD_int i = 0; i < nlocal; i++) {
    v[i * PAD + 0] += dtforce * f[i * PAD + 0];
    v[i * PAD + 1] += dtforce * f[i * PAD + 1];
    v[i * PAD + 2] += dtforce * f[i * PAD + 2];
  }
}

void Integrate::run(Atom &atom, Force *force, Neighbor &neighbor, Comm &comm,
                    Thermo &thermo, Timer &timer) {
  int i, n;

  comm.timer = &timer;
  timer.array[TIME_TEST] = 0.0;

  int check_safeexchange = comm.check_safeexchange;

  mass = atom.mass;
  dtforce = dtforce / mass;

  // Calculate middle timestep for checkpoint
  int checkpoint_step = ntimes / 2;

  // Get MPI info for communication phase
  int me = 0, nprocs = 1;
  MPI_Comm_rank(MPI_COMM_WORLD, &me);
  MPI_Comm_size(MPI_COMM_WORLD, &nprocs);

// Use OpenMP threads only within the following loop containing the main loop.
// Do not use OpenMP for setup and postprocessing.
#pragma omp parallel private(i, n)
  {
    int next_sort = sort_every > 0 ? sort_every : ntimes + 1;

    for (n = 0; n < ntimes; n++) {

#pragma omp barrier

      x = atom.x;
      v = atom.v;
      f = atom.f;
      xold = atom.xold;
      nlocal = atom.nlocal;

      initialIntegrate();

#pragma omp master
      timer.stamp();

      if ((n + 1) % neighbor.every) {

        comm.communicate(atom);
#pragma omp master
        timer.stamp(TIME_COMM);

      } else {
        // these routines are not yet ported to OpenMP
        {
          if (check_safeexchange) {
#pragma omp master
            {
              double d_max = 0;

              for (i = 0; i < atom.nlocal; i++) {
                double dx = (x[i * PAD + 0] - xold[i * PAD + 0]);

                if (dx > atom.box.xprd)
                  dx -= atom.box.xprd;

                if (dx < -atom.box.xprd)
                  dx += atom.box.xprd;

                double dy = (x[i * PAD + 1] - xold[i * PAD + 1]);

                if (dy > atom.box.yprd)
                  dy -= atom.box.yprd;

                if (dy < -atom.box.yprd)
                  dy += atom.box.yprd;

                double dz = (x[i * PAD + 2] - xold[i * PAD + 2]);

                if (dz > atom.box.zprd)
                  dz -= atom.box.zprd;

                if (dz < -atom.box.zprd)
                  dz += atom.box.zprd;

                double d = dx * dx + dy * dy + dz * dz;

                if (d > d_max)
                  d_max = d;
              }

              d_max = sqrt(d_max);

              if ((d_max > atom.box.xhi - atom.box.xlo) ||
                  (d_max > atom.box.yhi - atom.box.ylo) ||
                  (d_max > atom.box.zhi - atom.box.zlo))
                printf("Warning: Atoms move further than your subdomain size, "
                       "which will eventually cause lost atoms.\n"
                       "Increase reneighboring frequency or choose a different "
                       "processor grid\n"
                       "Maximum move distance: %lf; Subdomain dimensions: %lf "
                       "%lf %lf\n",
                       d_max, atom.box.xhi - atom.box.xlo,
                       atom.box.yhi - atom.box.ylo,
                       atom.box.zhi - atom.box.zlo);
            }
          }

#pragma omp master
          timer.stamp_extra_start();
          comm.exchange(atom);
          if (n + 1 >= next_sort) {
            atom.sort(neighbor);
            next_sort += sort_every;
          }
          comm.borders(atom);
#pragma omp master
          {
            timer.stamp_extra_stop(TIME_TEST);
            timer.stamp(TIME_COMM);
          }

          if (check_safeexchange)
            for (int i = 0; i < PAD * atom.nlocal; i++)
              xold[i] = x[i];
        }

#pragma omp barrier

        neighbor.build(atom);

        // #pragma omp barrier

#pragma omp master
        timer.stamp(TIME_NEIGH);
      }

      force->evflag = (n + 1) % thermo.nstat == 0;
      force->compute(atom, neighbor, comm, comm.me);

#pragma omp master
      timer.stamp(TIME_FORCE);

      if (neighbor.halfneigh && neighbor.ghost_newton) {
        comm.reverse_communicate(atom);

#pragma omp master
        timer.stamp(TIME_COMM);
      }

      v = atom.v;
      f = atom.f;
      nlocal = atom.nlocal;

#pragma omp barrier

      finalIntegrate();

      if (thermo.nstat)
        thermo.compute(n + 1, atom, neighbor, force, timer, comm);

      // Break out of parallel region at checkpoint step for I/O
      if (ckpt_at_end && (n + 1) == checkpoint_step) {
#pragma omp master
        {
          if (me == 0) {
            std::printf("\n========================================\n");
            std::printf("Reached mid-simulation checkpoint at timestep %d (out "
                        "of %d)\n",
                        n + 1, ntimes);
            std::printf("Exiting parallel region for I/O...\n");
            std::printf("========================================\n");
          }
        }
        break; // Exit the parallel loop to perform checkpoint
      }
    }
  } // end OpenMP parallel (first half)

  // -------------------------------------------------------
  // MID-SIMULATION SUSTAINED I/O CHECKPOINT (Gia's phase)
  // Performs checkpoint at the middle timestep
  // -------------------------------------------------------

  if (ckpt_at_end && checkpoint_step < ntimes) {
    if (me == 0) {
      std::printf("\n========================================\n");
      std::printf("Performing mid-simulation checkpoint with sustained I/O\n");
      std::printf("========================================\n");
    }

    // Signal I/O phase start to Python monitor
    if (me == 0) {
      FILE *fp = std::fopen("phase_marker.txt", "w");
      if (fp) {
        std::fprintf(fp, "IO_START\n");
        std::fclose(fp);
      }
    }

    write_checkpoint_sustained_io(atom, comm, checkpoint_step, ckpt_dir,
                                  ckpt_io_duration_sec, ckpt_chunk_bytes,
                                  ckpt_sleep_us, ckpt_fsync_chunks);

    // Signal I/O phase end
    if (me == 0) {
      FILE *fp = std::fopen("phase_marker.txt", "w");
      if (fp) {
        std::fprintf(fp, "IO_END\n");
        std::fclose(fp);
      }
    }

    // -------------------------------------------------------
    // COMMUNICATION PHASE (Johnnie)
    // Rank 0 sends total checkpoint data through MPI loopback
    // Other ranks wait at barrier (idle → low frequency)
    // -------------------------------------------------------

    if (comm_phase_enabled) {
      simulate_network_communication(atom, nprocs, comm_standin_bytes,
                                     comm_chunk_kb);
    }

    if (me == 0) {
      std::printf("\n========================================\n");
      std::printf("Resuming simulation for remaining %d timesteps\n",
                  ntimes - checkpoint_step);
      std::printf("========================================\n");
    }

    // Signal compute phase resume
    if (me == 0) {
      FILE *fp = std::fopen("phase_marker.txt", "w");
      if (fp) {
        std::fprintf(fp, "COMPUTE_RESUME\n");
        std::fclose(fp);
      }
    }

// Resume simulation for second half
#pragma omp parallel private(i, n)
    {
      int next_sort = sort_every > 0 ? sort_every : ntimes + 1;

      for (n = checkpoint_step; n < ntimes; n++) {

#pragma omp barrier

        x = atom.x;
        v = atom.v;
        f = atom.f;
        xold = atom.xold;
        nlocal = atom.nlocal;

        initialIntegrate();

#pragma omp master
        timer.stamp();

        if ((n + 1) % neighbor.every) {

          comm.communicate(atom);
#pragma omp master
          timer.stamp(TIME_COMM);

        } else {
          // these routines are not yet ported to OpenMP
          {
            if (check_safeexchange) {
#pragma omp master
              {
                double d_max = 0;

                for (i = 0; i < atom.nlocal; i++) {
                  double dx = (x[i * PAD + 0] - xold[i * PAD + 0]);

                  if (dx > atom.box.xprd)
                    dx -= atom.box.xprd;

                  if (dx < -atom.box.xprd)
                    dx += atom.box.xprd;

                  double dy = (x[i * PAD + 1] - xold[i * PAD + 1]);

                  if (dy > atom.box.yprd)
                    dy -= atom.box.yprd;

                  if (dy < -atom.box.yprd)
                    dy += atom.box.yprd;

                  double dz = (x[i * PAD + 2] - xold[i * PAD + 2]);

                  if (dz > atom.box.zprd)
                    dz -= atom.box.zprd;

                  if (dz < -atom.box.zprd)
                    dz += atom.box.zprd;

                  double d = dx * dx + dy * dy + dz * dz;

                  if (d > d_max)
                    d_max = d;
                }

                d_max = sqrt(d_max);

                if ((d_max > atom.box.xhi - atom.box.xlo) ||
                    (d_max > atom.box.yhi - atom.box.ylo) ||
                    (d_max > atom.box.zhi - atom.box.zlo))
                  printf("Warning: Atoms move further than your subdomain "
                         "size, which will eventually cause lost atoms.\n"
                         "Increase reneighboring frequency or choose a "
                         "different processor grid\n"
                         "Maximum move distance: %lf; Subdomain dimensions: "
                         "%lf %lf %lf\n",
                         d_max, atom.box.xhi - atom.box.xlo,
                         atom.box.yhi - atom.box.ylo,
                         atom.box.zhi - atom.box.zlo);
              }
            }

#pragma omp master
            timer.stamp_extra_start();
            comm.exchange(atom);
            if (n + 1 >= next_sort) {
              atom.sort(neighbor);
              next_sort += sort_every;
            }
            comm.borders(atom);
#pragma omp master
            {
              timer.stamp_extra_stop(TIME_TEST);
              timer.stamp(TIME_COMM);
            }

            if (check_safeexchange)
              for (int i = 0; i < PAD * atom.nlocal; i++)
                xold[i] = x[i];
          }

#pragma omp barrier

          neighbor.build(atom);

          // #pragma omp barrier

#pragma omp master
          timer.stamp(TIME_NEIGH);
        }

        force->evflag = (n + 1) % thermo.nstat == 0;
        force->compute(atom, neighbor, comm, comm.me);

#pragma omp master
        timer.stamp(TIME_FORCE);

        if (neighbor.halfneigh && neighbor.ghost_newton) {
          comm.reverse_communicate(atom);

#pragma omp master
          timer.stamp(TIME_COMM);
        }

        v = atom.v;
        f = atom.f;
        nlocal = atom.nlocal;

#pragma omp barrier

        finalIntegrate();

        if (thermo.nstat)
          thermo.compute(n + 1, atom, neighbor, force, timer, comm);
      }
    } // end OpenMP parallel (second half)
  }
}
