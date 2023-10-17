eval "$(micromamba shell hook --shell bash)"
micromamba create -p ./env
micromamba activate ./env/
micromamba install -c conda-forge pymeep=*=mpi_mpich_* nlopt -y
