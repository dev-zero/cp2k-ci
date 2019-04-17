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
        self.tree_cache = {}

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
    def get_subtree_sha(self, tree_entry, path):
        path_parts = path.split("/")
        if not path_parts:
            return tree_entry['sha']
        tree = gh.get(tree_entry['url'])
        for entry in tree['tree']:
            if entry['path'] == path_parts[0]:
                return self.get_subtree_sha(entry, "/".join(path_parts[1:]))
        raise Exception("Could not find {} in tree {}".format(path_parts[0], tree_entry['url']))


def main():
    print("hello")
    gh = GithubUtil("cp2k")
    sha = "760d482e266ee6cf23aa553ef04dc27b1c3cf3b2"
    commit = gh.get("/commits/"+sha)
    subtree = get_subtree_sha(gh, commit['commit']['tree'], "tools/docker/")
    pprint(subtree)
main()
# EOF
