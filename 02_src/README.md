# 02_src

## Directory Purpose
This directory contains the modified source code for the proxy application.

## Key Contents
- **`miniMD/`**: A heavily-modified instance of the proxy application from the Mantevo suite. 
  - **`integrate.cpp`**: Contains the critical instrumentation that publishes `COMPUTE`, `COMMUNICATE`, and `I/O` phase hints directly to a POSIX shared-memory table (`/dev/shm`).

## Usage Notes
The codebase must be compiled with the appropriate compiler flags (found in `04_configs`) to enable the OpenMPI bindings required for the multi-rank executions. Do not modify the shared-memory structs without also updating the corresponding Python monitor in `03_scripts`.
