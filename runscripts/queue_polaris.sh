NUM_NODES=2
qsub -A APSDataAnalysis -q debug -l select=${NUM_NODES}:system=polaris -l walltime=0:15:00 -l filesystems=home:eagle -l place=scatter /eagle/projects/APSDataAnalysis/mprince/lau/dev/laue-parallel/runscripts/run_polaris.sh