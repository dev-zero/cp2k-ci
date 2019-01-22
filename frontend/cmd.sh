#!/bin/bash -e

# author: Ole Schuett

cp -vf /opt/cp2kci-frontend/letsencrypt.ini /etc/letsencrypt/cli.ini

# bootstrap letsencrypt
/usr/sbin/apachectl start

echo "Obtaining Letsencrypt certificates..."
if [ ! -z "${LETSENCRYPT_STAGING+set}" ]; then
    echo "Using certbot --staging"
    certbot --staging certonly
else
    certbot certonly
fi

# start cron for cert renewal
service cron start

# start serving https
/usr/sbin/a2ensite ci.cp2k.org
/usr/sbin/apachectl restart

tail -f /var/log/apache2/*.log

#EOF
