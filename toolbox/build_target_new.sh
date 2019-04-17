#!/bin/bash -e

# author: Ole Schuett

set -eo pipefail

if (( $# < 4 )) ; then
    echo "Usage: build_target.sh <REPO> <GIT_REF> <DOCKERFILE> <IMAGE_TAG> <REPORT_UPLOAD_URL> [build-args]"
    exit 1
fi

REPO=$1
GIT_REF=$2
DOCKERFILE=$3
IMAGE_TAG=$4
REPORT_UPLOAD_URL=$5
shift 5

REPORT=/tmp/build_report.txt

echo -n "StartDate: "                     |& tee -a $REPORT
date --utc --rfc-3339=seconds             |& tee -a $REPORT

echo -n "CpuId:"                          |& tee -a $REPORT
cpuid -1 | grep "(synth)"                 |& tee -a $REPORT

/opt/cp2kci-toolbox/start_docker.sh       |& tee -a $REPORT
REPO_URL="https://github.com/cp2k/${REPO}.git"
BUILD_DATE=$(date --rfc-3339=seconds --utc)

cd /tmp
git clone --depth=1 --single-branch -b master ${REPO_URL} |& tee -a $REPORT
cd ${REPO}
git fetch origin ${GIT_REF}                               |& tee -a $REPORT
git -c advice.detachedHead=false checkout ${GIT_REF}      |& tee -a $REPORT
git submodule update --init --recursive                   |& tee -a $REPORT
cd (dirname ${DOCKERFILE})
git --no-pager log -1 --pretty='%nCommitSHA: %H%nCommitTime: %ci%nCommitAuthor: %an%nCommitSubject: %s%n' . |& tee -a $REPORT

docker build \
 --label "org.label-schema.schema-version=1.0" \
 --label "org.label-schema.vendor=CP2K-CI" \
 --label "org.label-schema.vcs-url=${REPO_URL}" \
 --label "org.label-schema.vcs-ref=${GIT_REF}" \
 --label "org.label-schema.build-date=${BUILD_DATE}" \
 --tag ${IMAGE_TAG} --file $(basename ${DOCKERFILE}) "$@" . |& tee -a $REPORT

docker image push ${IMAGE_TAG} |& tee -a $REPORT

# Wrap up.
echo -n "EndDate: "           |& tee -a $REPORT
date --utc --rfc-3339=seconds |& tee -a $REPORT

wget --quiet --output-document=- --method=PUT --header="content-type: text/plain;charset=utf-8" --header="cache-control: no-cache" --body-file="${REPORT}" "${REPORT_UPLOAD_URL}"

echo "Done :-)"

#EOF
