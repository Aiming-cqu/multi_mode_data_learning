#!/bin/sh

# Keep CPU-side CV workloads stable under high request concurrency.
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

# Disable OpenCL path for better runtime consistency in server mode.
export OPENCV_FOR_THREADS_NUM=1
export OPENCV_LOG_LEVEL='ERROR'
export OPENCV_OPENCL_RUNTIME='disabled'
