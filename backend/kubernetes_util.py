# author: Ole Schuett

import kubernetes
from uuid import uuid4
from os import path
from datetime import datetime, timedelta

from requests.auth import HTTPBasicAuth
import google.auth.transport.requests
import google.auth

class KubernetesUtil:
    def __init__(self, config, output_bucket, image_base, namespace="default"):
        try:
            kubernetes.config.load_kube_config()
        except Exception:
            kubernetes.config.load_incluster_config()
        self.config = config
        self.output_bucket = output_bucket
        self.image_base = image_base
        self.namespace = namespace
        self.api = kubernetes.client
        self.batch_api = kubernetes.client.BatchV1Api()
        self.image_cache = {}

    # --------------------------------------------------------------------------
    def get_upload_url(self, path, content_type="text/plain;charset=utf-8"):
        expiration = datetime.utcnow() + timedelta(hours=12)
        blob = self.output_bucket.blob(path)
        upload_url = blob.generate_signed_url(expiration, method='PUT',
                                              content_type=content_type)
        return upload_url

    # --------------------------------------------------------------------------
    def list_jobs(self, selector):
        return self.batch_api.list_namespaced_job(self.namespace,
                                                  label_selector=selector)

    # --------------------------------------------------------------------------
    def delete_job(self, job_name):
        print("deleting job: " + job_name)
        self.batch_api.delete_namespaced_job(job_name, self.namespace,
                                             propagation_policy="Background")

    # --------------------------------------------------------------------------
    def patch_job_annotations(self, job_name, new_annotations):
        new_job_metadata = self.api.V1ObjectMeta(annotations=new_annotations)
        new_job = self.api.V1Job(metadata=new_job_metadata)
        self.batch_api.patch_namespaced_job(job_name, self.namespace, new_job)

    # --------------------------------------------------------------------------
    def resources(self, target):
        cpu = self.config.getint(target, "cpu")
        req_cpu = 0.97 * cpu   # Request 3% less to leave some for kubernetes.
        return self.api.V1ResourceRequirements(requests={"cpu": req_cpu})

    # --------------------------------------------------------------------------
    def affinity(self, target):
        nodepools = self.config.get(target, "nodepools").split()
        requirement = self.api.V1NodeSelectorRequirement(
            key='cloud.google.com/gke-nodepool',
            operator='In', values=nodepools)
        term = self.api.V1NodeSelectorTerm(match_expressions=[requirement])
        selector = self.api.V1NodeSelector([term])
        node_affinity = self.api.V1NodeAffinity(
            required_during_scheduling_ignored_during_execution=selector)
        return self.api.V1Affinity(node_affinity=node_affinity)

    # --------------------------------------------------------------------------
    def submit_run_new(self, target, git_branch, git_ref, job_annotations, priority=None):

        print("NEW: Submitting run for target: {}.".format(target))

        # metadata
        job_name = "run-" + target + "-" + str(uuid4())[:8]
        job_annotations['cp2kci/target'] = target
        job_metadata = self.api.V1ObjectMeta(name=job_name,
                                             labels={'cp2kci': 'run'},
                                             annotations=job_annotations)

        # pod
        tolerate_costly = self.api.V1Toleration(key="costly", operator="Exists")
        pod_spec = self.api.V1PodSpec(init_containers=[],
                                      containers=[],
                                      volumes=[],
                                      tolerations=[tolerate_costly],
                                      termination_grace_period_seconds=0,
                                      restart_policy="Never",
                                      dns_policy="Default",  # bypass kube-dns
                                      affinity=self.affinity(target),
                                      automount_service_account_token=False,
                                      priority_class_name=priority)
        pod_template = self.api.V1PodTemplateSpec(spec=pod_spec)

        # job
        job_spec = self.api.V1JobSpec(template=pod_template,
                                      backoff_limit=6,
                                      active_deadline_seconds=7200)  # 2 hours
        job = self.api.V1Job(spec=job_spec, metadata=job_metadata)

        image = self.add_build_container(job, target, git_ref)
        self.add_run_container(job, target, git_branch, git_ref, image)

        self.batch_api.create_namespaced_job(self.namespace, body=job)


    # --------------------------------------------------------------------------
    def add_build_container(self, job, target, commit_sha):

        dockerfile = self.config.get(target, "dockerfile")
        dockerdir = path.dirname(dockerfile)
        docker_tree_sha = gh.get_tree_sha(commit_sha, dockerdir)
        cache_key = docker_tree_sha  #TODO: add build-args
        run_image = self.image_base + "img_{}:{}".format(target, cache_key)

        if image_exists(run_image):
            return run_image

        # upload wait message
        buildlog_url = self.get_upload_url(job.metadata.name + "_buildlog.txt")
        buildlog_blob = self.output_bucket.blob(report_path)
        buildlog_blob.cache_control = "no-cache"
        buildlog_blob.upload_from_string("Build log not yet available.")

        repo = self.config.get(target, "repository")
        command = ["./build_target_new.sh", repo, commit_sha, dockerfile, run_image, buildlog_url]

        # build-args
        if self.config.has_option(target, "build_args"):
            for arg in self.config.get(target, "build_args").split():
                command.append("--build-arg")
                command.append(arg.replace("${IMAGE_BASE}", self.image_base))

        # make sure image gets push to run_image

        # docker volume (needed for performance)
        docker_source = self.api.V1EmptyDirVolumeSource()
        docker_volname = "volume-" + job_name
        docker_volume = self.api.V1Volume(name=docker_volname,
                                          empty_dir=docker_source)
        docker_mount = self.api.V1VolumeMount(mount_path="/var/lib/docker/",
                                              name=docker_volname)

        # secret stuff
        secret_name = "backend-gcp-key"
        secret_source = self.api.V1SecretVolumeSource(secret_name=secret_name)
        secret_volume = self.api.V1Volume(name="backend-gcp-key-volume",
                                          secret=secret_source)
        secret_mount = self.api.V1VolumeMount(name="backend-gcp-key-volume",
                                              mount_path="/var/secrets/google",
                                              read_only=True)
        secret_env = self.api.V1EnvVar(name="GOOGLE_APPLICATION_CREDENTIALS",
                                       value="/var/secrets/google/key.json")

        # container with privileged=True as needed by docker build
        privileged = self.api.V1SecurityContext(privileged=True)
        toolbox_image = self.image_base + "img_cp2kci_toolbox:latest"
        container = self.api.V1Container(name="build",
                                         image=toolbox_image,
                                         resources=self.resources(target),
                                         command=command,
                                         volume_mounts=[docker_mount,
                                                        secret_mount],
                                         security_context=privileged,
                                         env=[secret_env])

        # add to job
        job.metadata.annotations['cp2kci/buildlog_path'] = buildlog_path
        job.spec.template.spec.volumes.append(docker_mount)
        job.spec.template.spec.volumes.append(secret_mount)
        job.spec.template.spec.init_containers.append(container)

        return run_image


    # --------------------------------------------------------------------------
    def add_run_container(self, job, target, git_branch, git_ref, image):
        #TODO: Do we really need git_branch? Couldn't we just fetch the commit_sha?
        report_path = job.metadata.name + "_report.txt"
        artifacts_path = job.metadata.name + "_artifacts.tgz"

        # upload wait message
        report_blob = self.output_bucket.blob(report_path)
        report_blob.cache_control = "no-cache"
        report_blob.upload_from_string("Report not yet available.")

        # environment variables
        env_vars = {}
        env_vars["GIT_BRANCH"] = git_branch
        env_vars["GIT_REF"] = git_ref
        env_vars["REPORT_UPLOAD_URL"] = self.get_upload_url(report_path)
        env_vars["ARTIFACTS_UPLOAD_URL"] = \
            self.get_upload_url(artifacts_path, content_type="application/gzip")
        k8s_env_vars = [self.api.V1EnvVar(k, v) for k, v in env_vars.items()]

        # container with SYS_PTRACE as needed by LeakSanitizer.
        caps = self.api.V1Capabilities(add=["SYS_PTRACE"])
        security = self.api.V1SecurityContext(capabilities=caps)
        container = self.api.V1Container(name="run",
                                         image=image,
                                         resources=self.resources(target),
                                         security_context=security,
                                         env=k8s_env_vars)

        # add to job
        job.metadata.annotations['cp2kci/report_path'] = report_path
        job.metadata.annotations['cp2kci/artifacts_path'] = artifacts_path
        job.spec.template.spec.containers.append(container)


    # --------------------------------------------------------------------------
    def image_label_exists(self, image):
        #TODO: maybe move into a new gcr_util.py
        if image in self.image_cache:
            return True

        # https://hackernoon.com/inspecting-docker-images-without-pulling-them-4de53d34a604
        # https://cloud.google.com/container-registry/docs/advanced-authentication
        scopes = ["https://www.googleapis.com/auth/devstorage.read_only"]
        credentials, project = google.auth.default(scopes=scopes)
        auth_request = google.auth.transport.requests.Request()
        credentials.refresh(auth_request)
        auth = HTTPBasicAuth('_token', credentials.token)
        headers = {"Accept": "application/vnd.docker.distribution.manifest.v2+json"}

        assert image.startswith("gcr.io")
        image_without_tag = image.rsplit(":", 1)[0]
        image_name = image_without_tag[6:]  # strip off gcr.io
        url = "https://gcr.io/v2/" + image_basename + "/tags/list"
        r = requests.get(url, headers=headers, auth=auth)
        r.raise_for_status()
        for tag in r.json()['tags']:
            self.image_cache.add(image_without_tag + ":" + tag)

        return image in self.image_cache

    # --------------------------------------------------------------------------
    def submit_run(self, target, env_vars, job_annotations, priority=None):
        print("Submitting run for target: {}.".format(target))

        job_name = "run-" + target + "-" + str(uuid4())[:8]
        report_path = job_name + "_report.txt"
        artifacts_path = job_name + "_artifacts.tgz"

        # upload wait message
        report_blob = self.output_bucket.blob(report_path)
        report_blob.cache_control = "no-cache"
        report_blob.upload_from_string("Report not yet available.")

        # environment variables
        env_vars["REPORT_UPLOAD_URL"] = self.get_upload_url(report_path)
        env_vars["ARTIFACTS_UPLOAD_URL"] = \
            self.get_upload_url(artifacts_path, content_type="application/gzip")
        k8s_env_vars = [self.api.V1EnvVar(k, v) for k, v in env_vars.items()]

        # metadata
        job_annotations['cp2kci/target'] = target
        job_annotations['cp2kci/report_path'] = report_path
        job_annotations['cp2kci/artifacts_path'] = artifacts_path
        job_metadata = self.api.V1ObjectMeta(name=job_name,
                                             labels={'cp2kci': 'run'},
                                             annotations=job_annotations)

        # container with SYS_PTRACE as needed by LeakSanitizer.
        caps = self.api.V1Capabilities(add=["SYS_PTRACE"])
        security = self.api.V1SecurityContext(capabilities=caps)
        image = self.image_base + "img_{}:latest".format(target)
        container = self.api.V1Container(name="main",
                                         image=image,
                                         resources=self.resources(target),
                                         security_context=security,
                                         env=k8s_env_vars)

        # pod
        tolerate_costly = self.api.V1Toleration(key="costly", operator="Exists")
        pod_spec = self.api.V1PodSpec(containers=[container],
                                      tolerations=[tolerate_costly],
                                      termination_grace_period_seconds=0,
                                      restart_policy="Never",
                                      dns_policy="Default",  # bypass kube-dns
                                      affinity=self.affinity(target),
                                      automount_service_account_token=False,
                                      priority_class_name=priority)
        pod_template = self.api.V1PodTemplateSpec(spec=pod_spec)

        # job
        job_spec = self.api.V1JobSpec(template=pod_template,
                                      backoff_limit=6,
                                      active_deadline_seconds=7200)  # 2 hours
        job = self.api.V1Job(spec=job_spec, metadata=job_metadata)
        self.batch_api.create_namespaced_job(self.namespace, body=job)

        return job_name

    # --------------------------------------------------------------------------
    def submit_build(self, target):
        print("Submitting build for target: {}.".format(target))
        job_name = "build-" + target + "-" + str(uuid4())[:8]
        report_url = self.get_upload_url(job_name + "_report.txt")
        repo = self.config.get(target, "repository")
        dockerfile = self.config.get(target, "dockerfile")
        command = ["./build_target.sh", target, repo, dockerfile, report_url]

        # build-args
        if self.config.has_option(target, "build_args"):
            for arg in self.config.get(target, "build_args").split():
                command.append("--build-arg")
                command.append(arg.replace("${IMAGE_BASE}", self.image_base))

        # docker volume (needed for performance)
        docker_source = self.api.V1EmptyDirVolumeSource()
        docker_volname = "volume-" + job_name
        docker_volume = self.api.V1Volume(name=docker_volname,
                                          empty_dir=docker_source)
        docker_mount = self.api.V1VolumeMount(mount_path="/var/lib/docker/",
                                              name=docker_volname)

        # secret stuff
        secret_name = "backend-gcp-key"
        secret_source = self.api.V1SecretVolumeSource(secret_name=secret_name)
        secret_volume = self.api.V1Volume(name="backend-gcp-key-volume",
                                          secret=secret_source)
        secret_mount = self.api.V1VolumeMount(name="backend-gcp-key-volume",
                                              mount_path="/var/secrets/google",
                                              read_only=True)
        secret_env = self.api.V1EnvVar(name="GOOGLE_APPLICATION_CREDENTIALS",
                                       value="/var/secrets/google/key.json")

        # container with privileged=True as needed by docker build
        privileged = self.api.V1SecurityContext(privileged=True)
        image = self.image_base + "img_cp2kci_toolbox:latest"
        container = self.api.V1Container(name="main",
                                         image=image,
                                         resources=self.resources(target),
                                         command=command,
                                         volume_mounts=[docker_mount,
                                                        secret_mount],
                                         security_context=privileged,
                                         env=[secret_env])

        # pod
        tolerate_costly = self.api.V1Toleration(key="costly", operator="Exists")
        pod_spec = self.api.V1PodSpec(containers=[container],
                                      volumes=[docker_volume, secret_volume],
                                      tolerations=[tolerate_costly],
                                      termination_grace_period_seconds=0,
                                      restart_policy="Never",
                                      dns_policy="Default",  # bypass kube-dns
                                      affinity=self.affinity(target),
                                      automount_service_account_token=False)
        pod_template = self.api.V1PodTemplateSpec(spec=pod_spec)

        # job
        job_spec = self.api.V1JobSpec(template=pod_template,
                                      backoff_limit=1,
                                      active_deadline_seconds=7200)  # 2 hours

        job_meta = self.api.V1ObjectMeta(name=job_name,
                                         labels={'cp2kci': 'build'})
        job = self.api.V1Job(spec=job_spec, metadata=job_meta)
        self.batch_api.create_namespaced_job(self.namespace, body=job)

        return job_name

# EOF
