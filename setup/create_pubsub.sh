#!/bin/bash -e

# author: Ole Schuett

set -x

gcloud beta pubsub topics create cp2kci-topic

# Try re-delivery every 9 minutes up to 30 minutes, ie. max 3 times.
gcloud beta pubsub subscriptions create \
  cp2kci-subscription \
  --topic=cp2kci-topic \
  --message-retention-duration=30m \
  --ack-deadline=540

#EOF
