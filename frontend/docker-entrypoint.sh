#!/bin/sh
set -eu
# Only substitute selected env vars so nginx variables like $host stay intact.
case "${BACKEND_UPSTREAM}" in
  https://*)
    PROXY_SSL_VERIFY="proxy_ssl_verify on;
        proxy_ssl_trusted_certificate /etc/ssl/certs/ca-certificates.crt;
        proxy_ssl_verify_depth 3;"
    ;;
  *)
    PROXY_SSL_VERIFY="# http upstream: TLS certificate verification is not used"
    ;;
esac
export PROXY_SSL_VERIFY
envsubst '${BACKEND_UPSTREAM} ${PROXY_SSL_VERIFY}' \
  < /etc/nginx/templates/default.conf.template \
  > /etc/nginx/conf.d/default.conf
exec nginx -g 'daemon off;'
