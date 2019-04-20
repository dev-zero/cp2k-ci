#!/bin/bash -e

# author: Ole Schuett

PROJECT=$(gcloud config list --format 'value(core.project)')
BACKEND_ACCOUNT="cp2kci-backend@${PROJECT}.iam.gserviceaccount.com"
RUNNER_ACCOUNT="cp2kci-runner@${PROJECT}.iam.gserviceaccount.com"
CRONJOB_ACCOUNT="cp2kci-cronjob@${PROJECT}.iam.gserviceaccount.com"

set -x

# kubectl delete secrets backend-gcp-key github-app-key

gcloud iam service-accounts keys create key.json --iam-account ${BACKEND_ACCOUNT}
kubectl create secret generic backend-gcp-key --from-file="key.json"
rm key.json

gcloud iam service-accounts keys create key.json --iam-account ${RUNNER_ACCOUNT}
kubectl create secret generic runner-gcp-key --from-file="key.json"
rm key.json

gcloud iam service-accounts keys create key.json --iam-account ${CRONJOB_ACCOUNT}
kubectl create secret generic cronjob-gcp-key --from-file="key.json"
rm key.json

# some more secrets
kubectl create secret generic github-app-key --from-file="github-app-key.pem"

#EOF
