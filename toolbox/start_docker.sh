#!/bin/bash -e

# author: Ole Schuett

/usr/bin/dockerd -H unix:// &> /var/log/dockerd.log &
sleep 1  # wait a bit for docker deamon
docker version

if [[ "$?" != "0" ]]; then
    cat /var/log/docker.log
    echo "Docker does not work, not running with --privileged?"
    exit 1
fi

#https://issuetracker.google.com/issues/38098801
gcloud auth activate-service-account --key-file=$GOOGLE_APPLICATION_CREDENTIALS
#gcloud auth list
#gcloud config list account


gcloud auth configure-docker --quiet

#EOF
