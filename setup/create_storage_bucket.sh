#!/bin/bash -e

# author: Ole Schuett

BUCKET="cp2k-ci"

set -x

gsutil mb -c regional -l us-central1 gs://${BUCKET}
gsutil iam ch allUsers:objectViewer gs://${BUCKET}

#EOF
