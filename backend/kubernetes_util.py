# author: Ole Schuett

import kubernetes
from uuid import uuid4
from datetime import datetime, timedelta

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
    def submit_run(self, target, git_ref, job_annotations, priority=None):
        print("Submitting run for target: {}.".format(target))

        job_name = "run-" + target + "-" + str(uuid4())[:8]
        report_path = job_name + "_report.txt"
        artifacts_path = job_name + "_artifacts.tgz"

        # upload waiting message
        report_blob = self.output_bucket.blob(report_path)
        report_blob.cache_control = "no-cache"
        report_blob.upload_from_string("Report not yet available.")

        # environment variables
        env_vars = {}
        env_vars["TARGET"] = target
        env_vars["GIT_REF"] = git_ref
        env_vars["GIT_REPO"] = self.config.get(target, "repository")
        env_vars["DOCKERFILE"] = self.config.get(target, "dockerfile")
        env_vars["REPORT_UPLOAD_URL"] = self.get_upload_url(report_path)
        env_vars["ARTIFACTS_UPLOAD_URL"] = \
            self.get_upload_url(artifacts_path, content_type="application/gzip")

        # special treatment for cp2k toolchain based targets
        toolchain = self.config.getboolean(target, "toolchain", fallback=False)
        assert not toolchain or env_vars["GIT_REPO"] == "cp2k"
        env_vars["TOOLCHAIN"] = "yes" if toolchain else "no"

        # metadata
        job_annotations['cp2kci/target'] = target
        job_annotations['cp2kci/report_path'] = report_path
        job_annotations['cp2kci/artifacts_path'] = artifacts_path
        job_metadata = self.api.V1ObjectMeta(name=job_name,
                                             labels={'cp2kci': 'run'},
                                             annotations=job_annotations)

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
        env_vars["GOOGLE_APPLICATION_CREDENTIALS"] = "/var/secrets/google/key.json"

        # container with privileged=True as needed by docker build
        privileged = self.api.V1SecurityContext(privileged=True)
        toolbox_image = self.image_base + "/img_cp2kci_toolbox:latest"
        k8s_env_vars = [self.api.V1EnvVar(k, v) for k, v in env_vars.items()]
        container = self.api.V1Container(name="main",
                                         image=toolbox_image,
                                         resources=self.resources(target),
                                         command=["./run_target.sh"],
                                         volume_mounts=[docker_mount,
                                                        secret_mount],
                                         security_context=privileged,
                                         env=k8s_env_vars)

        # pod
        tolerate_costly = self.api.V1Toleration(key="costly", operator="Exists")
        pod_spec = self.api.V1PodSpec(containers=[container],
                                      volumes=[docker_volume, secret_volume],
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

# EOF
