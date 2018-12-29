#!/bin/bash -e

# author: Ole Schuett

CLUSTER_NAME="cp2k-cluster"

set -x

# node-taints are still a beta feature

for CPUS in 8 16 32 ; do
    #gcloud container node-pools delete pool-highcpu-${CPUS}-haswell
    gcloud beta container node-pools create pool-highcpu-${CPUS}-haswell \
       --cluster="${CLUSTER_NAME}" \
       --machine-type="n1-highcpu-${CPUS}" \
       --min-cpu-platform="Intel Haswell" \
       --preemptible \
       --enable-autoupgrade \
       --enable-autorepair \
       --enable-autoscaling \
       --max-nodes=4 \
       --min-nodes=0 \
       --num-nodes=0 \
       --node-taints="costly=true:NoSchedule"

    gcloud beta container node-pools create pool-highcpu-${CPUS}-skylake \
        --cluster="${CLUSTER_NAME}" \
        --machine-type="n1-highcpu-${CPUS}" \
        --min-cpu-platform="Intel Skylake" \
        --preemptible \
        --enable-autoupgrade \
        --enable-autorepair \
        --enable-autoscaling \
        --max-nodes=4 \
        --min-nodes=0 \
        --num-nodes=0 \
        --node-taints="costly=true:NoSchedule"
done

#EOF
