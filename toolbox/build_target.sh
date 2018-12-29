#!/bin/bash -e

# author: Ole Schuett

set -eo pipefail

if (( $# < 4 )) ; then
    echo "Usage: build_target.sh <TARGET> <REPO> <DOCKERFILE> <REPORT_UPLOAD_URL> [build-args]"
    exit 1
fi

TARGET=$1
REPO=$2
DOCKERFILE=$3
REPORT_UPLOAD_URL=$4
shift 4

REPORT=/tmp/build_${TARGET}_report.txt

echo -n "StartDate: "                     |& tee -a $REPORT
date --utc --rfc-3339=seconds             |& tee -a $REPORT

echo -n "CpuId:"                          |& tee -a $REPORT
cpuid -1 | grep "(synth)"                 |& tee -a $REPORT

/opt/cp2kci-toolbox/start_docker.sh       |& tee -a $REPORT

PROJECT=$(gcloud config list --format 'value(core.project)')

cd /tmp
git clone --depth=1 --single-branch -b master https://github.com/cp2k/${REPO}.git |& tee -a $REPORT
cd ${REPO}$(dirname ${DOCKERFILE})
git --no-pager log -1 --pretty='%nCommitSHA: %H%nCommitTime: %ci%nCommitAuthor: %an%nCommitSubject: %s%n' . |& tee -a $REPORT

IMAGE_TAG=gcr.io/${PROJECT}/img_${TARGET}:latest
docker build -t ${IMAGE_TAG} -f $(basename ${DOCKERFILE}) "$@" . |& tee -a $REPORT
docker image push ${IMAGE_TAG}                                   |& tee -a $REPORT

# Wrap up.
echo -n "EndDate: "           |& tee -a $REPORT
date --utc --rfc-3339=seconds |& tee -a $REPORT

wget --quiet --output-document=- --method=PUT --header="content-type: text/plain;charset=utf-8" --header="cache-control: no-cache" --body-file="${REPORT}" "${REPORT_UPLOAD_URL}"

echo "Done :-)"

#EOF
