# author: Ole Schuett

import os
import jwt
import requests
from time import time
from pathlib import Path
from datetime import datetime

GITHUB_APP_ID = os.environ['GITHUB_APP_ID']
GITHUB_APP_KEY = Path(os.environ['GITHUB_APP_KEY']).read_text()
GITHUB_APP_INSTALL_ID = os.environ['GITHUB_APP_INSTALL_ID']


class GithubUtil:
    def __init__(self, repo):
        self.repo = repo
        self.token = self.get_installation_token()  # TODO make this lazy
        self.repo_url = "https://api.github.com/repos/cp2k/" + repo
        self.tree_cache = {}

    # --------------------------------------------------------------------------
    def get_master_head_sha(self):
        # Get sha of latest git commit.
        return self.get("/commits")[0]['sha']

    # --------------------------------------------------------------------------
    def get_tree_sha(self, commit_sha, tree_path):
        # Get sha of tree for given path and commit.
        cache_key = "{}:{}".format(commit_sha, tree_path)
        if cache_key in self.tree_cache:
            return self.tree_cache[cache_key]

        assert tree_path.startswith("/") and tree_path.endswith("/")
        commit = self.get("/commits/"+commit_sha)
        current_tree_sha = commit['commit']['tree']['sha']

        for directory in tree_path.split("/")[1:-1]:
            tree = self.get("/git/trees/"+current_tree_sha)
            matches = [e['sha'] for e in tree['tree'] if e['path'] == directory]
            if len(matches) != 1:
                raise Exception("Could not find directory {} in tree {}".format(directory, current_tree_sha))
            current_tree_sha = matches[0]

        self.tree_cache[cache_key] = current_tree_sha
        return current_tree_sha

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
        headers = {"Authorization": "token " + self.token,
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

# EOF
