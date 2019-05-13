#!/bin/bash -e

# author: Ole Schuett

# Remove old GCP container images.

echo "Looking for old images..."

for IMAGE in $(gcloud container images list --format="get(name)"); do
    if [[ $IMAGE == *"img_cp2kci_"* ]]; then
        FILTER="-tags:(latest)"
    elif [[ $IMAGE == *"img_cp2k-toolchain"* ]]; then
        MAX_AGE_DAYS=30
        FILTER="timestamp.datetime < -P${MAX_AGE_DAYS}D AND -tags:(master)"
    else
        MAX_AGE_DAYS=3
        FILTER="timestamp.datetime < -P${MAX_AGE_DAYS}D"
    fi

    for SHA in $(gcloud container images list-tags --filter="${FILTER}" --format="get(digest)" "${IMAGE}"); do
        gcloud --quiet container images delete --force-delete-tags "${IMAGE}@${SHA}"
    done
done

# Cloud storage is cleaned via lifecycle management.

#EOF
