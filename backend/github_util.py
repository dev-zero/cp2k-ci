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

    # --------------------------------------------------------------------------
    def get_master_head_sha(self):
        # Get sha of latest git commit.
        return self.get("/commits")[0]['sha']

    # --------------------------------------------------------------------------
    def print_rate_limit(self, response):
        remaining = response.headers.get('X-RateLimit-Remaining', None)
        if remaining and int(remaining) < 100:
            print("X-RateLimit-Remaining: {}".format(remaining))

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
        self.print_rate_limit(r)
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
        self.print_rate_limit(r)
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
        self.print_rate_limit(r)
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
        self.print_rate_limit(r)
        if r.status_code >= 400:
            print(r.text)
        r.raise_for_status()
        return r.json()

# EOF
