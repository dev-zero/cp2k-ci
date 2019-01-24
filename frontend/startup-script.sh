#!/bin/bash -e

# author: Ole Schuett

# mount disk
mkdir -p /mnt/disks/letsencrypt
if ! mount /dev/sdb /mnt/disks/letsencrypt ; then
  mkfs.ext4 -m 0 -F -E lazy_itable_init=0,lazy_journal_init=0,discard /dev/sdb
  mount /dev/sdb /mnt/disks/letsencrypt
fi

# fetch metadata
function get_metadata {
   wget -O- -q --header="Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/$1"
}
PROJECT=$(get_metadata "project/project-id")
GITHUB_WEBHOOK_SECRET=$(get_metadata "instance/attributes/GITHUB_WEBHOOK_SECRET")
LETSENCRYPT_STAGING=$(get_metadata "instance/attributes/LETSENCRYPT_STAGING")

# setup docker using a workaround for /root being readonly with cos
export HOME=/home/chronos/
docker-credential-gcr configure-docker

# launch container
docker run --init --detach \
   --publish 80:80 --publish 443:443 \
   --volume "/mnt/disks/letsencrypt:/etc/letsencrypt" \
   --env GITHUB_WEBHOOK_SECRET=${GITHUB_WEBHOOK_SECRET} \
   --env LETSENCRYPT_STAGING=${LETSENCRYPT_STAGING} \
   gcr.io/${PROJECT}/img_cp2kci_frontend:latest

#EOF
