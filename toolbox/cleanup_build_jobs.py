#!/usr/bin/python3

# author: Ole Schuett

import kubernetes
from datetime import datetime, timezone, timedelta

def main():
    try:
        kubernetes.config.load_kube_config()
    except Exception:
        kubernetes.config.load_incluster_config()
    namespace = "default"
    batch_api = kubernetes.client.BatchV1Api()

    job_list = batch_api.list_namespaced_job(namespace,
                                             label_selector='cp2kci=build')

    for job in job_list.items:
        if job.status.active:
            continue
        if job.status.failed:
            continue
        if not job.status.succeeded:
            continue
        if not job.status.completion_time:
            continue
        age = datetime.now(timezone.utc) - job.status.completion_time
        if age > timedelta(days=1):
            job_name = job.metadata.name
            print("deleting job: " + job_name)
            batch_api.delete_namespaced_job(job_name, namespace, {})


main()

#EOF