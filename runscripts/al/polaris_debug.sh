NUM_NODES=2
RANKS_PER_NODE=32
START_IM=0
PROJ_NAME=laue_al_debug

AFFINITY_PATH=../runscripts/set_gpu_affinity.sh
PYTHON_PATH=/eagle/projects/APSDataAnalysis/mprince/lau_env_polaris/bin/python 
CONFIG_PATH=../configs/AL30/config-64.yml

echo "
cd \${PBS_O_WORKDIR}

# MPI and OpenMP settings
NNODES=\`wc -l < \$PBS_NODEFILE\`
NRANKS_PER_NODE=${RANKS_PER_NODE}
NDEPTH=2
NTHREADS=2

NTOTRANKS=\$(( NNODES * NRANKS_PER_NODE ))
echo \"NUM_OF_NODES= \${NNODES} TOTAL_NUM_RANKS= \${NTOTRANKS} RANKS_PER_NODE= \${NRANKS_PER_NODE} THREADS_PER_RANK= \${NTHREADS}\"

mpiexec -n \${NTOTRANKS} --ppn \${NRANKS_PER_NODE} --depth=\${NDEPTH} --cpu-bind depth --env OMP_NUM_THREADS=\${NTHREADS} -env OMP_PLACES=threads \\
    ${AFFINITY_PATH} \\
    ${PYTHON_PATH} \\
    ../laue_parallel.py \\
    ${CONFIG_PATH} \\
    --start_im ${START_IM} \\
    --mpi_recon

mpiexec -n \${NTOTRANKS} --ppn \${NRANKS_PER_NODE} --depth=\${NDEPTH} --cpu-bind depth --env OMP_NUM_THREADS=\${NTHREADS} -env OMP_PLACES=threads \\
    ${AFFINITY_PATH} \\
    ${PYTHON_PATH} \\
    ../recon_parallel.py \\
    ${CONFIG_PATH} \\
    --start_im ${START_IM} \\
" | \
qsub -A APSDataAnalysis \
-q debug \
-l select=${NUM_NODES}:system=polaris \
-l walltime=1:00:00 \
-l filesystems=home:eagle \
-l place=scatter \
-N ${PROJ_NAME} 