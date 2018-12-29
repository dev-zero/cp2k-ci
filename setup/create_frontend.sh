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

gcloud compute disks create ${DISK_NAME} --size="1GB"

# --container-mount-disk is still beta
gcloud beta compute instances create-with-container \
   "cp2kci-frontend" \
   --machine-type="f1-micro" \
   --container-image="gcr.io/${PROJECT}/img_cp2kci_frontend:latest" \
   --disk="name=${DISK_NAME}" \
   --container-mount-disk="name=${DISK_NAME},mount-path=/etc/letsencrypt/" \
   --tags="http-server,https-server" \
   --address="35.208.181.14" \
   --service-account="${FRONTEND_ACCOUNT}" \
   --container-env="GITHUB_WEBHOOK_SECRET=${GITHUB_WEBHOOK_SECRET}"

   #--metadata="google-logging-enabled=false" \
   #--metadata="google-monitoring-enabled=false"

   #--container-env="LETSENCRYPT_STAGING=1"
   #--public-ptr-domain="ci.cp2k.org" \
#EOF
