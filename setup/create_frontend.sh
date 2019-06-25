#!/bin/bash -e

# author: Ole Schuett

if [ -z "${GITHUB_WEBHOOK_SECRET}" ]; then
    echo "Please set \$GITHUB_WEBHOOK_SECRET"
    exit 1
fi

DISK_NAME="cp2kci-letsencrypt"
PROJECT=$(gcloud config list --format 'value(core.project)')
FRONTEND_ACCOUNT_NAME="cp2kci-frontend"
FRONTEND_ACCOUNT="${FRONTEND_ACCOUNT_NAME}@${PROJECT}.iam.gserviceaccount.com"

set -x

#gcloud compute disks create ${DISK_NAME} --size="1GB"

gcloud compute instances create \
   "cp2kci-frontend" \
   --machine-type="f1-micro" \
   --image-project="cos-cloud" \
   --image-family="cos-stable" \
   --address="35.222.79.114" \
   --disk="name=${DISK_NAME}" \
   --tags="http-server,https-server" \
   --service-account="${FRONTEND_ACCOUNT}" \
   --metadata-from-file="startup-script=../frontend/startup-script.sh" \
   --metadata="GITHUB_WEBHOOK_SECRET=${GITHUB_WEBHOOK_SECRET},LETSENCRYPT_STAGING=${LETSENCRYPT_STAGING}"

#EOF
