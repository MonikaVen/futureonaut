#!/bin/sh
set -eu
# Only substitute BACKEND_UPSTREAM so nginx vars like $host stay intact
envsubst '${BACKEND_UPSTREAM}' \
  < /etc/nginx/templates/default.conf.template \
  > /etc/nginx/conf.d/default.conf
exec nginx -g 'daemon off;'
