#!/bin/bash -e

# author: Ole Schuett

PROJECT=$(gcloud config list --format 'value(core.project)')
FRONTEND_ACCOUNT="cp2kci-frontend@${PROJECT}.iam.gserviceaccount.com"
BACKEND_ACCOUNT="cp2kci-backend@${PROJECT}.iam.gserviceaccount.com"

set -x

gcloud iam service-accounts create ${FRONTEND_ACCOUNT_NAME} --display-name="cp2kci-frontend"
gcloud iam service-accounts create ${BACKEND_ACCOUNT_NAME} --display-name="cp2kci-backend"

#EOF
