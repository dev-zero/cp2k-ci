#!/bin/bash -e

# author: Ole Schuett

gcloud compute firewall-rules create default-allow-http \
    --direction="ingress" \
    --action="allow" \
    --target-tags="http-server" \
    --rules tcp:80

gcloud compute firewall-rules create default-allow-https \
    --direction="ingress" \
    --action="allow" \
    --target-tags="https-server" \
    --rules tcp:443

#EOF
