#!/usr/bin/python3

# author: Ole Schuett

import sys
import requests
from requests.auth import HTTPBasicAuth
import google.auth.transport.requests
import google.auth

# https://hackernoon.com/inspecting-docker-images-without-pulling-them-4de53d34a604
# https://cloud.google.com/container-registry/docs/advanced-authentication

def main():
    if len(sys.argv) != 2:
        print("get_image_labels.py <image-name>")
        sys.exit(1)

    image = sys.argv[1]

    scopes = ["https://www.googleapis.com/auth/devstorage.read_only"]
    credentials, project = google.auth.default(scopes=scopes)
    auth_request = google.auth.transport.requests.Request()
    credentials.refresh(auth_request)

    auth = HTTPBasicAuth('_token', credentials.token)
    headers = {"Accept": "application/vnd.docker.distribution.manifest.v2+json"}
    base_url = "https://gcr.io/v2/" + project + "/" + image

    url = base_url + "/manifests/latest"
    r = requests.get(url, headers=headers, auth=auth)
    digest = r.json()['config']['digest']

    url = base_url + "/blobs/" + digest
    r = requests.get(url, headers=headers, auth=auth)
    labels = r.json()['config']['Labels']

    for key in sorted(labels.keys()):
        print("{:<35}  {}".format(key, labels[key]))

main()

#EOF
