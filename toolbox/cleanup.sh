#!/bin/bash -e

# author: Ole Schuett

# Remove GCP container images that are not tagged. Typically. the only tag is "latest".

for IMAGE in $(gcloud container images list --format="get(name)"); do
   for SHA in $(gcloud container images list-tags --filter='-tags:(latest)' --format='get(digest)' $IMAGE); do
       gcloud --quiet container images delete --force-delete-tags ${IMAGE}@${SHA}
   done
done

#EOF
