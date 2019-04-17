#!/usr/bin/python3
# author: Ole Schuett

import os
#import jwt
import requests
from time import time
from pathlib import Path
from datetime import datetime
from pprint import pprint

#GITHUB_APP_ID = os.environ['GITHUB_APP_ID']
#GITHUB_APP_KEY = Path(os.environ['GITHUB_APP_KEY']).read_text()
#GITHUB_APP_INSTALL_ID = os.environ['GITHUB_APP_INSTALL_ID']

class GithubUtil:
    def __init__(self, repo):
        self.repo = repo
        #self.token = self.get_installation_token()  # TODO make this lazy
        self.repo_url = "https://api.github.com/repos/cp2k/" + repo
        self.cache = {}

    # --------------------------------------------------------------------------
    def get_master_head_sha(self):
        # Get sha of latest git commit.
        return self.get("/commits")[0]['sha']

    # --------------------------------------------------------------------------
    def get_installation_token(self):
        # Create App JWT token.
        now = int(time())
        payload = {"iat": now,
                   "exp": now + 600,  # expiration time (10 minute maximum)
                   "iss": GITHUB_APP_ID}
        app_token = jwt.encode(payload, GITHUB_APP_KEY, algorithm="RS256")
        # Setup header for app.
        headers = {
            "Authorization": "Bearer ".encode("utf8") + app_token,
            "Accept": "application/vnd.github.machine-man-preview+json",
        }
        # Obtain installation access token.
        url = "https://api.github.com/app/installations/{}/access_tokens"
        r = requests.post(url.format(GITHUB_APP_INSTALL_ID), headers=headers)
        return r.json()['token']

    # --------------------------------------------------------------------------
    def now(self):
        return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    # --------------------------------------------------------------------------
    def age(self, created_at):
        # TODO: Python 3.7 has datetime.fromisoformat().
        creation = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
        return datetime.utcnow() - creation

    # --------------------------------------------------------------------------
    def get(self, url):
        if url.startswith("/"):
            url = self.repo_url + url
        headers = {#"Authorization": "token " + self.token,
                   "Accept": "application/vnd.github.antiope-preview+json"}
        r = requests.get(url, headers=headers)
        if r.status_code >= 400:
            print(r.text)
        r.raise_for_status()
        return r.json()

    # --------------------------------------------------------------------------
    def post(self, url, body):
        if url.startswith("/"):
            url = self.repo_url + url
        headers = {"Authorization": "token " + self.token,
                   "Accept": "application/vnd.github.antiope-preview+json"}
        r = requests.post(url, headers=headers, json=body)
        if r.status_code >= 400:
            print(r.text)
        r.raise_for_status()
        return r.json()

    # --------------------------------------------------------------------------
    def patch(self, url, body):
        if url.startswith("/"):
            url = self.repo_url + url
        headers = {"Authorization": "token " + self.token,
                   "Accept": "application/vnd.github.antiope-preview+json"}
        r = requests.patch(url, headers=headers, json=body)
        if r.status_code >= 400:
            print(r.text)
        r.raise_for_status()
        return r.json()


    # --------------------------------------------------------------------------
    def get_tree_sha(self, commit_sha, path):
        cache_key = "tree:{}:{}".format(commit_sha, path)
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        commit = self.get("/commits/"+commit_sha)
        current_tree_sha = commit['commit']['tree']['sha']

        assert path.startswith("/") and path.endswith("/")
        for directory in path.split("/")[1:-1]:
            tree = self.get("/git/trees/"+current_tree_sha)
            matches = [e['sha'] for e in tree['tree'] if e['path'] == directory]
            if len(matches) != 1:
                raise Exception("Could not find directory {} in tree {}".format(directory, current_tree_sha))
            current_tree_sha = matches[0]

        self.cache[cache_key] = current_tree_sha
        return current_tree_sha
      
      
from requests.auth import HTTPBasicAuth
import google.auth.transport.requests
import google.auth

# --------------------------------------------------------------------------
def image_label_exists(image, label):
    cache_key = image + ":" + label
    if cache_key in image_label_cache:
        return True

    # https://hackernoon.com/inspecting-docker-images-without-pulling-them-4de53d34a604
    # https://cloud.google.com/container-registry/docs/advanced-authentication
    scopes = ["https://www.googleapis.com/auth/devstorage.read_only"]
    credentials, project = google.auth.default(scopes=scopes)
    auth_request = google.auth.transport.requests.Request()
    credentials.refresh(auth_request)
    auth = HTTPBasicAuth('_token', credentials.token)
    headers = {"Accept": "application/vnd.docker.distribution.manifest.v2+json"}
    url = "https://gcr.io/v2/" + project + "/" + image + "/tags/list"
    r = requests.get(url, headers=headers, auth=auth)
    r.raise_for_status()    
    for tag in r.json()['tags']:
        existing_images.add(image + ":" + tag)
        
    return cache_key in image_label_cache
    
def main():
    image_exists("img_cp2k-coverage-pdbg", "asdf")
    return
    print("hello")
    gh = GithubUtil("cp2k")
    commit_sha = "760d482e266ee6cf23aa553ef04dc27b1c3cf3b2"
    tree_sha = gh.get_tree_sha(commit_sha, "/tools/docker/")
    print(tree_sha)
    #print("/".split("/"))
    #subtree = get_subtree_sha(gh, commit['commit']['tree'], "tools/docker/")
    #pprint(subtree)
main()
# EOF
