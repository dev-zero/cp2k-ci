#!/usr/bin/python3

# author: Ole Schuett

import re
import sys
import json
import traceback
import configparser
from time import sleep
from datetime import datetime, timedelta, timezone

from github_util import GithubUtil
from kubernetes_util import KubernetesUtil

import google.auth
import google.cloud.pubsub
import google.cloud.storage

gcp_project = google.auth.default()[1]
storage_client = google.cloud.storage.Client(project=gcp_project)
subscriber_client = google.cloud.pubsub.SubscriberClient()
output_bucket = storage_client.get_bucket("cp2k-ci")

KNOWN_TAGS = ("required_check_run", "optional_check_run", "dashboard", "exclude_build_all")
config = configparser.ConfigParser()
config.read("./cp2k-ci.conf")

kubeutil = KubernetesUtil(config=config, output_bucket=output_bucket,
                          image_base="gcr.io/{}/".format(gcp_project))


#===================================================================================================
def main():
    print("starting")

    # check config tags
    for target in config.sections():
        tags = config.get(target, "tags").split()
        assert all([t in KNOWN_TAGS for t in tags])

    # subscribe to pubsub
    sub_name = 'projects/' + gcp_project + '/subscriptions/cp2kci-subscription'
    subscriber_client.subscribe(sub_name, process_pubsub_message)

    print("starting main loop")
    for i in range(sys.maxsize):
        try:
            tick(i)
        except:
            print(traceback.format_exc())
        sleep(5)

#===================================================================================================
def tick(cycle):
    run_job_list = kubeutil.list_jobs('cp2kci=run')
    if cycle % 30 == 0:  # every 2.5 minutes
        poll_pull_requests(run_job_list)
    for job in run_job_list.items:
        if "cp2kci/dashboard" in job.metadata.annotations:
            publish_job_to_dashboard(job)
        if "cp2kci/check_run_url" in job.metadata.annotations:
            publish_job_to_github(job)
        if job.status.completion_time:
            kubeutil.delete_job(job.metadata.name)

    # remove successful build jobs
    build_job_list = kubeutil.list_jobs('cp2kci=build')
    for job in build_job_list.items:
        if job.status.completion_time and not job.status.failed:
            kubeutil.delete_job(job.metadata.name)

#===================================================================================================
def process_pubsub_message(message):
    try:
        data = json.loads(message.data)
        rpc = data.pop('rpc')
        process_rpc(rpc, **data)
        message.ack()  # ack late in case we get preempted in the middle
    except:
        print(traceback.format_exc())
        message.ack()  # prevent crash looping

#===================================================================================================
def process_rpc(rpc, **args):
    print("Got RPC: " + rpc)

    if rpc == 'echo':
        print("Got args: ", args)

    elif rpc == 'update_healthz_beacon':
        blob = output_bucket.blob("healthz_beacon.txt")
        blob.cache_control = "no-cache"
        blob.upload_from_string(datetime.utcnow().isoformat())

    elif rpc == 'github_event':
        process_github_event(args['event'], args['body'])

    elif rpc == 'submit_all_builds':
        for target in config.sections():
            tags = config.get(target, "tags").split()
            if "exclude_build_all" not in tags:
                kubeutil.submit_build(target)

    elif rpc == 'submit_build':
        target = args['target']
        kubeutil.submit_build(target)

    elif rpc == 'submit_all_dashboard_tests':
        head_sha = GithubUtil("cp2k").get_master_head_sha()
        for target in config.sections():
            tags = config.get(target, "tags").split()
            if "dashboard" in tags:
                submit_dashboard_test(target, head_sha)

    elif rpc == 'submit_dashboard_test':
        target = args['target']
        head_sha = GithubUtil("cp2k").get_master_head_sha()
        submit_dashboard_test(target, head_sha, force=True)

    elif rpc == 'submit_check_run':
        repo = args['repo']
        pr_number = args['pr_number']
        target = args['target']
        gh = GithubUtil(repo)
        pr = gh.get("/pulls/{}".format(pr_number))
        submit_check_run(target, gh, pr, sender="_somebody_")

    elif rpc == 'process_pull_request':
        repo = args['repo']
        pr_number = args['pr_number']
        gh = GithubUtil(repo)
        process_pull_request(gh, pr_number, sender="_somebody_")

    else:
        print("Unknown RPC: " + rpc)

#===================================================================================================
def process_github_event(event, body):
    action = body.get("action", "")
    print("Got github even: {} action: {}".format(event, action))

    if event == "pull_request" and action in ("opened", "synchronize"):
        pr_number = body["number"]
        repo = body["repository"]["name"]
        gh = GithubUtil(repo)
        sender = body["sender"]["login"]
        process_pull_request(gh, pr_number, sender)

    elif event == "check_suite" and action == "rerequested":
        # snatch pr_number from existing check_runs
        repo = body["repository"]["name"]
        gh = GithubUtil(repo)
        check_run_list = gh.get(body["check_suite"]["check_runs_url"])
        ext_id = check_run_list['check_runs'][0]["external_id"]
        pr_number, _ = parse_external_id(ext_id)
        sender = body["sender"]["login"]
        process_pull_request(gh, pr_number, sender)

    elif event == "check_run" and action == "rerequested":
        ext_id = body["check_run"]["external_id"]
        pr_number, target = parse_external_id(ext_id)
        repo = body["repository"]["name"]
        gh = GithubUtil(repo)
        pr = gh.get("/pulls/{}".format(pr_number))
        sender = body["sender"]["login"]
        submit_check_run(target, gh, pr, sender)

    elif event == "check_run" and action == "requested_action":
        ext_id = body["check_run"]["external_id"]
        pr_number, target = parse_external_id(ext_id)
        requested_action = body["requested_action"]["identifier"]
        sender = body["sender"]["login"]
        if requested_action == "run":
            repo = body["repository"]["name"]
            gh = GithubUtil(repo)
            pr = gh.get("/pulls/{}".format(pr_number))
            submit_check_run(target, gh, pr, sender)
        else:
            print("Unknown requested action: {}".format(requested_action))
    else:
        pass # Unhandled github even - there are many of these.

#===================================================================================================
def await_mergeability(gh, pr, check_run_name):
    # https://developer.github.com/v3/git/#checking-mergeability-of-pull-requests

    if pr['mergeable'] is not None:
        return

    # This might take a while, tell the user and disable resubmit buttons.
    check_run = {
        "name": check_run_name,
        "head_sha": pr['head']['sha'],
        "started_at": gh.now(),
        "output": {"title": "Waiting for mergeability check", "summary": ""}
    }
    gh.post("/check-runs", check_run)

    pr_number = pr['number']
    for i in range(10):
        print("Waiting for mergeability check of PR {}".format(pr_number))
        sleep(5)
        pr.clear()
        pr.update(gh.get("/pulls/{}".format(pr_number)))
        if pr['mergeable'] is not None:
            return

    # timeout
    check_run['completed_at']: gh.now()
    check_run['conclusion'] = 'failure'
    check_run['output'] = {"title": "Mergeability check timeout.", "summary": ""}
    gh.post("/check-runs", check_run)
    raise Exception("Mergeability check timeout on PR {}".format(pr_number))

#===================================================================================================
def process_pull_request(gh, pr_number, sender):
    pr = gh.get("/pulls/{}".format(pr_number))

    # check branch
    if pr['base']['ref'] != 'master':
        print("Ignoring PR for non-master branch: " + pr['base']['ref'])
        return

    # check git history
    check_run = {
        "name": "Git History",
        "external_id": format_external_id(pr['number'], "git-history"),
        "head_sha": pr['head']['sha'],
        "started_at": gh.now(),
        "completed_at": gh.now(),
    }

    commits = gh.get(pr['commits_url'])
    await_mergeability(gh, pr,  check_run['name'])

    if not pr['mergeable']:
        check_run['conclusion'] = 'failure'
        check_run['output'] = {"title": "Branch not mergeable.", "summary": ""}
    elif any([len(c['parents']) != 1 for c in commits]):
        check_run['conclusion'] = 'failure'
        help_url = "https://github.com/cp2k/cp2k/wiki/CP2K-CI#git-history-contains-merge-commits"
        check_run['output'] = {"title": "Git history contains merge commits.",
                               "summary": "[How to fix this?]({})".format(help_url)}
    else:
        check_run['conclusion'] = 'success'
        check_run['output'] = {"title": "Git history is fine.", "summary": ""}

    gh.post("/check-runs", check_run)
    if check_run['conclusion'] == 'failure':
        print("Git history test failed - not processing PR further.")
        return

    # submit / create check_runs
    for target in config.sections():
        tags = config.get(target, "tags").split()
        if "required_check_run" in tags:
            submit_check_run(target, gh, pr, sender)
        if "optional_check_run" in tags:
            create_optional_check_run(target, gh, pr)

#===================================================================================================
def format_external_id(pr_number, target):
        return "{};{}".format(pr_number, target)

def parse_external_id(ext_id):
    pr_number = int(ext_id.split(";")[0])
    target = ext_id.split(";")[1]
    return pr_number, target

#===================================================================================================
def create_optional_check_run(target, gh, pr):
    check_run = {
        "name": config.get(target, "display_name"),
        "external_id": format_external_id(pr['number'], target),
        "head_sha": pr['head']['sha'],
        "started_at": gh.now(),
        "completed_at": gh.now(),
        "conclusion": "neutral",
        "output": {"title": "Trigger manually on demand.", "summary": ""},
        "actions": [{
            "label": "Run test",
            "identifier": "run",
            "description": "Trigger test manually",
        }]
    }
    gh.post("/check-runs", check_run)

#===================================================================================================
def submit_check_run(target, gh, pr, sender):
    check_run = {
        "name": config.get(target, "display_name"),
        "external_id": format_external_id(pr['number'], target),
        "head_sha": pr['head']['sha'],
    }

    # check if any related files were modified
    if config.has_option(target, "related_path"):
        related_path_re = re.compile(config.get(target, "related_path"))
        modified_files = [e['filename'] for e in gh.get(pr['url'] + '/files')]
        if not any([related_path_re.match(fn) for fn in modified_files]):
            summary = "No files related to regtests were changed - skipping."
            check_run["output"] = {"title":summary, "summary": ""}
            check_run["started_at"] = gh.now()
            check_run["completed_at"] = gh.now()
            check_run["conclusion"] = "success"
            gh.post("/check-runs", check_run)
            return

    await_mergeability(gh, pr,  check_run['name'])

    # related files were modified, let's submit job.
    check_run = gh.post("/check-runs", check_run)
    job_annotations = {
        'cp2kci/sender': sender,
        'cp2kci/pull_request_html_url': pr['html_url'],
        'cp2kci/check_run_url': check_run['url'],
        'cp2kci/check_run_html_url': check_run['html_url'],
        'cp2kci/check_run_status': 'queued',
    }
    env_vars = {
        'GIT_BRANCH': "pull/{}/merge".format(pr['number']),
        'GIT_REF': pr['merge_commit_sha'],
    }
    if sender=="oschuett":
        kubeutil.submit_run_new(target,
            git_branch=env_vars['GIT_BRANCH'],
            git_ref=env_vars['GIT_REF'],
            job_annotations=job_annotations,
            priority="high-priority")
    else:
        kubeutil.submit_run(target, env_vars, job_annotations, "high-priority")

#===================================================================================================
def submit_dashboard_test(target, head_sha, force=False):
    assert config.get(target, "repository") == "cp2k"
    assert target.startswith("cp2k-")
    test_name = target[5:]

    # Download first 1kb of report and compare against CommitSHA.
    latest_report_sha = None
    report_fn = "dashboard_"+test_name+"_report.txt"
    blob = output_bucket.get_blob(report_fn)
    if blob:
        report_txt = blob.download_as_string(end=1024).decode("utf8")
        m = re.search("(^|\n)CommitSHA: (\w{40})\n", report_txt)
        if m:
            latest_report_sha = m.group(2)

    if latest_report_sha != head_sha or force:
        job_annotations = {'cp2kci/dashboard': 'yes'}
        env_vars = {'GIT_BRANCH': "master", 'GIT_REF': head_sha}
        kubeutil.submit_run(target, env_vars, job_annotations)

#===================================================================================================
def poll_pull_requests(job_list):
    """ A save guard in case we're missing a callback or loosing BatchJob """

    active_check_runs_urls = []
    for job in job_list.items:
        annotations = job.metadata.annotations
        if not job.status.active and job.status.failed:
            continue  # job failed
        if "cp2kci/check_run_url" in annotations:
            active_check_runs_urls.append(annotations['cp2kci/check_run_url'])

    all_repos = set([config.get(t, "repository") for t in config.sections()])
    for repo in all_repos:
        gh = GithubUtil(repo)
        for pr in gh.get("/pulls"):
            if pr['base']['ref'] != 'master':
                continue  # ignore non-master PR
            head_sha = pr['head']['sha']

            check_run_list = gh.get("/commits/{}/check-runs".format(head_sha))
            for check_run in check_run_list['check_runs']:
                if check_run['status'] == 'completed':
                    continue  # Good, check_run is completed.
                if check_run['url'] in active_check_runs_urls:
                    continue  # Good, there is still an active BatchJob.
                if gh.age(check_run['started_at']) < timedelta(minutes=3):
                    continue # It's still young - wait a bit.

                print("Found forgotten check_run: {}".format(check_run['url']))
                summary = "Something in the CI system went wrong :-("
                check_run["conclusion"] = "failure"
                check_run["completed_at"] = gh.now()
                check_run["output"] = {"title":summary, "summary": ""}
                gh.patch(check_run['url'], check_run)

            pr_is_old = gh.age(pr['created_at']) > timedelta(minutes=3)
            if pr_is_old and check_run_list['total_count'] == 0:
                print("Found forgotten PR: {}".format(pr['number']))
                process_pull_request(gh, pr['number'], pr['user']['login'])

#===================================================================================================
def publish_job_to_dashboard(job):
    job_annotations = job.metadata.annotations
    if job.status.completion_time is None:
        return

    target = job_annotations['cp2kci/target']
    print("Publishing {} to dashboard.".format(target))
    assert config.get(target, "repository") == "cp2k"
    assert target.startswith("cp2k-")
    test_name = target[5:]

    src_blob = output_bucket.blob(job_annotations["cp2kci/report_path"])
    if src_blob.exists():
        dest_blob = output_bucket.blob("dashboard_"+test_name+"_report.txt")
        dest_blob.rewrite(src_blob)

    src_blob = output_bucket.blob(job_annotations["cp2kci/artifacts_path"])
    if src_blob.exists():
        dest_blob = output_bucket.blob("dashboard_"+test_name+"_artifacts.tgz")
        dest_blob.rewrite(src_blob)

#===================================================================================================
def publish_job_to_github(job):
    status = 'queued'
    if job.status.active:
        status = 'in_progress'
    elif job.status.completion_time:
        status = 'completed'

    # failed jobs are handled by poll_pull_requests()

    job_annotations = job.metadata.annotations
    if job_annotations['cp2kci/check_run_status'] == status:
        return # Nothing to do - check_run already uptodate.

    target = job_annotations['cp2kci/target']
    print("Publishing {} to Github.".format(target))
    repo = config.get(target, "repository")
    gh = GithubUtil(repo)

    report_blob = output_bucket.blob(job_annotations["cp2kci/report_path"])
    artifacts_blob = output_bucket.blob(job_annotations["cp2kci/artifacts_path"])
    check_run = {'status': status, 'output': {}}
    if status == 'completed':
        report = parse_report(report_blob)
        check_run['conclusion'] = 'success' if report['status']=='OK' else 'failure'
        check_run['completed_at'] = gh.now()
        check_run['output']['title'] = report['summary']
        summary = '[Detailed Report]({})'.format(report_blob.public_url)
        if artifacts_blob.exists():
            summary += '\n\n[Artifacts]({})'.format(artifacts_blob.public_url)
    else:
        check_run['output']['title'] = "In Progress..."
        summary = '[Live Report]({}) (updates every 30s)'.format(report_blob.public_url)

    sender = job_annotations['cp2kci/sender']
    summary += "\n\nTriggered by @{}.".format(sender)
    check_run['output']['summary'] = summary

    # update check_run
    gh.patch(job_annotations['cp2kci/check_run_url'], check_run)

    # update job_annotations
    job_annotations['cp2kci/check_run_status'] = status
    kubeutil.patch_job_annotations(job.metadata.name, job_annotations)

#===================================================================================================
def parse_report(report_blob):
    report = {'status':'UNKNOWN', 'summary': '', 'git-sha':None}
    try:
        report['summary'] = 'Error while retrieving report.'
        report_txt = report_blob.download_as_string().decode("utf8")

        report['summary'] = 'Error while parsing report.'
        report['summary'] = re.findall("(^|\n)Summary: (.+)\n", report_txt)[-1][1]
        report['status'] = re.findall("(^|\n)Status: (.+)\n", report_txt)[-1][1]
        report['git-sha'] = re.search("(^|\n)CommitSHA: (\w{40})\n", report_txt).group(2)
    except:
        print(traceback.format_exc())

    return(report)
#===================================================================================================
if __name__ == "__main__":
    main()

#EOF
