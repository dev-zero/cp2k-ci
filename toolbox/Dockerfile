FROM ubuntu:18.04

# author: Ole Schuett

USER root
WORKDIR /tmp

# install ubuntu packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    wget \
    less \
    git \
    gpg-agent \
    apt-transport-https \
    ca-certificates \
    software-properties-common \
    python3-pip \
    python3-wheel \
    python3-setuptools \
  && rm -rf /var/lib/apt/lists/*

# install python packages
COPY requirements.txt .
RUN pip3 install -r requirements.txt

# install latest cpuid tool
# The Ubuntu version does not recognize the GCP Skylake CPUs.
RUN wget -q https://www.cp2k.org/static/downloads/cpuid-20180519.x86_64.tar.gz && \
    echo "76b8f7334068c894152ef04bbb0b3ce8  cpuid-20180519.x86_64.tar.gz" | md5sum --check && \
    tar -xzf cpuid-20180519.x86_64.tar.gz && \
    cp ./cpuid-20180519/cpuid /usr/bin/

# install docker
RUN wget -O docker.gpg https://download.docker.com/linux/ubuntu/gpg && \
    apt-key add ./docker.gpg && \
    add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" && \
    apt-get update && \
    apt-get install -y docker-ce && \
    rm -rf /var/lib/apt/lists/*

# install gcloud
RUN wget -O gcloud.gpg https://packages.cloud.google.com/apt/doc/apt-key.gpg && \
    apt-key add gcloud.gpg && \
    add-apt-repository "deb http://packages.cloud.google.com/apt cloud-sdk-$(lsb_release -cs) main"  && \
    apt-get update && \
    apt-get install -y google-cloud-sdk && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /opt/cp2kci-toolbox
COPY *.sh *.py /opt/cp2kci-toolbox/

#EOF
