#!/bin/bash -e

# author: Ole Schuett

# Remove GCP container images that are not tagged. Typically. the only tag is "latest".

echo "Looking for old images..."
MAX_AGE_DAYS=30

for IMAGE in $(gcloud container images list --format="get(name)"); do
   for SHA in $(gcloud container images list-tags --filter="timestamp.datetime < -P${MAX_AGE_DAYS}D" --format="get(digest)" $IMAGE); do
       gcloud --quiet container images delete --force-delete-tags ${IMAGE}@${SHA}
   done
done

# Cloud storage is cleaned via lifecycle management.

#EOF
