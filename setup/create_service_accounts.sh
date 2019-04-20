#!/bin/bash -e

# author: Ole Schuett

set -x

# CAUTION: When deleting service-accounts also delete all associated AIM roles, otherwise GCP gets confused.

gcloud iam service-accounts create "cp2kci-frontend" --display-name="cp2kci-frontend"
gcloud iam service-accounts create "cp2kci-backend"  --display-name="cp2kci-backend"
gcloud iam service-accounts create "cp2kci-runner"   --display-name="cp2kci-runner"
gcloud iam service-accounts create "cp2kci-cronjob"  --display-name="cp2kci-cronjob"

#EOF
