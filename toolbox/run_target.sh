#!/bin/bash
# shellcheck disable=SC2155

# author: Ole Schuett

set -o pipefail

# Check input.
for key in TARGET DOCKERFILE TOOLCHAIN GIT_REPO GIT_BRANCH GIT_REF REPORT_UPLOAD_URL ARTIFACTS_UPLOAD_URL ; do
    value="$(eval echo \$${key})"
    if [ -z "$value" ] ; then
        echo "\$${key} is empty"
        exit 1
    fi
    echo "${key}=\"${value}\""
done

# Upload to cloud storage.
function upload_file {
    local url=$1
    local file=$2
    local content_type=$3
    wget --quiet --output-document=- --method=PUT --header="content-type: ${content_type}" --header="cache-control: no-cache" --body-file="${file}" "${url}" > /dev/null
}

# Append end date and upload report.
function upload_final_report {
    local end_date=$(date --utc --rfc-3339=seconds)
    echo -e "\nEndDate: ${end_date}" | tee -a "${REPORT}"
    upload_file "${REPORT_UPLOAD_URL}" "${REPORT}" "text/plain;charset=utf-8"
}

# Handle preemption gracefully.
function sigterm_handler {
    echo -e "\nThis job just got preempted. No worries, it should restart soon." | tee -a "${REPORT}"
    upload_final_report
    exit 1  # trigger retry
}
trap sigterm_handler SIGTERM

# Helper for building or pulling docker images.
function docker_pull_or_build {
    local this_target=$1
    local this_dockerfile=$2
    shift 2
    local build_args=( "$@" )

    # Compute cache key for docker image.
    local build_context="."$(dirname "${this_dockerfile}")
    local git_tree_sha=$(git ls-tree -d  HEAD "${build_context}" | awk '{print $3}')
    local build_args_hash=$(echo "${build_args[@]}" | md5sum | awk '{print $1}')
    local cpuid_hash=$(echo "${CPUID}" | md5sum | awk '{print $1}')
    local image_name="gcr.io/${PROJECT}/img_${this_target}-cpuid-${cpuid_hash::3}"
    local image_tag="gittree-${git_tree_sha::7}-buildargs-${build_args_hash::7}"
    local image_ref="${image_name}:${image_tag}"
    local cache_ref="${image_name}:${GIT_BRANCH//\//-}"

    echo -en "Trying to pull image ${this_target}... " | tee -a "${REPORT}"
    if docker image pull "${image_ref}" ; then
        echo "success :-)" >> "${REPORT}"
    else
        echo "image not found." >> "${REPORT}"
        echo -e "\n#################### Building Image ${this_target} ####################" | tee -a "${REPORT}"
        docker image pull "${cache_ref}" || docker image pull "${image_name}:master"
        if ! docker build \
               --cache-from "${cache_ref}" \
               --cache-from "${image_name}:master" \
               --tag "${image_ref}" \
               --file ".${this_dockerfile}" \
               "${build_args[@]}" "${build_context}" |& tee -a "${REPORT}" ; then
          echo -e "\nSummary: Docker build had non-zero exit status.\nStatus: FAILED" | tee -a "${REPORT}"
          upload_final_report
          exit 0  # Prevent crash looping.
        fi
        echo -en "\nPushing image ${this_target}... " | tee -a "${REPORT}"
        docker image push "${image_ref}"
        echo "done." >> "${REPORT}"
    fi

    docker tag "${image_ref}" "${cache_ref}"
    docker image push "${cache_ref}"

    # Export image_ref into gobal variable for subsequent docker build or run.
    IMAGE_REF=${image_ref}
}

#===============================================================================

# Write report header
REPORT=/tmp/report.txt
CPUID=$(cpuid -1 | grep "(synth)" | cut -c14-)
START_DATE=$(date --utc --rfc-3339=seconds)
echo -e "StartDate: ${START_DATE}\nCpuId: ${CPUID}" | tee -a "${REPORT}"

# Upload preliminary report every 30s in the background.
(
while true ; do
    sleep 1
    count=$(( (count + 1) % 30 ))
    if (( count == 1 )) && [ -n "${REPORT_UPLOAD_URL}" ]; then
        upload_file "${REPORT_UPLOAD_URL}" "${REPORT}" "text/plain;charset=utf-8"
    fi
done
)&

# Start docker deamon.
/opt/cp2kci-toolbox/start_docker.sh
PROJECT=$(gcloud config list --format 'value(core.project)')
PROJECT=${PROJECT:-"cp2k-org-project"}

# Update git repo which contains the Dockerfiles.
cd "/workspace/${GIT_REPO}" || exit
git fetch origin "${GIT_BRANCH}"
git -c advice.detachedHead=false checkout "${GIT_REF}"
git --no-pager log -1 --pretty='%nCommitSHA: %H%nCommitTime: %ci%nCommitAuthor: %an%nCommitSubject: %s%n' |& tee -a "${REPORT}"

# Pull or build docker containers.
if [ "${TOOLCHAIN}" == "yes" ] ; then
    docker_pull_or_build cp2k-toolchain /tools/toolchain/Dockerfile
    docker_pull_or_build "${TARGET}" "${DOCKERFILE}" --build-arg "TOOLCHAIN=${IMAGE_REF}"
else
    docker_pull_or_build "${TARGET}" "${DOCKERFILE}"
fi

echo -e "\n#################### Running Image ${TARGET} ####################" | tee -a "${REPORT}"
ARTIFACTS_DIR="/tmp/artifacts"
mkdir "${ARTIFACTS_DIR}"
if ! docker run --init --cap-add=SYS_PTRACE \
       --env "GIT_BRANCH=${GIT_BRANCH}" \
       --env "GIT_REF=${GIT_REF}" \
       --volume "${ARTIFACTS_DIR}:/workspace/artifacts" \
       "${IMAGE_REF}"  |& tee -a "${REPORT}" ; then
    echo -e "\nSummary: Docker run had non-zero exit status.\nStatus: FAILED" | tee -a "${REPORT}"
fi

# Upload artifacts.
if [ ! -z "$(ls -A ${ARTIFACTS_DIR})" ]; then
    echo -en "\nUploading artifacts... " | tee -a "${REPORT}"
    ARTIFACTS_TGZ="/tmp/artifacts.tgz"
    cd "${ARTIFACTS_DIR}" || exit
    tar -czf "${ARTIFACTS_TGZ}" -- *
    upload_file "${ARTIFACTS_UPLOAD_URL}" "${ARTIFACTS_TGZ}" "application/gzip"
    echo "done" >> "${REPORT}"
fi

upload_final_report
echo "Toolbox Done :-)"

#EOF
