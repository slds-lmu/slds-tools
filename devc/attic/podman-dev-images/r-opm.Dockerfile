ARG TAG=latest

FROM devc/r-base:${TAG}

USER root

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    software-properties-common \
 && add-apt-repository -y ppa:opm/ppa \
 && apt-get update \
 && apt-get install  -y --no-install-recommends \
    mpi-default-bin libopm-simulators-bin python3-opm-common \
 && apt-get purge -y --auto-remove software-properties-common \
 && apt-get clean && rm -rf /var/lib/apt/lists/*

USER dev
