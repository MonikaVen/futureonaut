#!/usr/bin/env bash
# Rebuild and roll out Futureonaut web + API containers.
# Does not create, replace, or reseed PostgreSQL. DATABASE_URL and other
# existing Container App environment variables are left unchanged.
set -euo pipefail

RG="${RG:-rg-futureonaut}"
WEB_APP="${WEB_APP:-futureonaut-web}"
API_APP="${API_APP:-futureonaut-api}"
WEB_IMAGE="${WEB_IMAGE:-futureonaut-frontend}"
API_IMAGE="${API_IMAGE:-futureonaut-backend}"
TAG="${TAG:-$(git -C "$(dirname "$0")/.." rev-parse --short HEAD)}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Using subscription $(az account show --query name -o tsv)"
echo "==> Resource group: $RG  tag: $TAG"
echo "==> PostgreSQL will not be created or modified."

if az postgres flexible-server list -g "$RG" --query "[].name" -o tsv >/dev/null 2>&1; then
  echo "==> Existing Postgres servers (left untouched):"
  az postgres flexible-server list -g "$RG" --query "[].{name:name,state:state}" -o table || true
fi

APP_JSON=$(az containerapp show -g "$RG" -n "$API_APP" -o json)
ACR_LOGIN=$(echo "$APP_JSON" | python3 -c "import json,sys
cfg=json.load(sys.stdin)
image=cfg['properties']['template']['containers'][0]['image']
print(image.split('/')[0])
")
if [[ -z "$ACR_LOGIN" || "$ACR_LOGIN" != *azurecr.io ]]; then
  echo "Could not infer ACR from $API_APP image" >&2
  exit 1
fi
ACR_NAME="${ACR_LOGIN%%.*}"

echo "==> Building backend image in ACR $ACR_NAME"
az acr build -r "$ACR_NAME" -t "${API_IMAGE}:${TAG}" -t "${API_IMAGE}:latest" "$ROOT/backend"

echo "==> Building frontend image in ACR $ACR_NAME"
az acr build -r "$ACR_NAME" -t "${WEB_IMAGE}:${TAG}" -t "${WEB_IMAGE}:latest" "$ROOT/frontend"

echo "==> Updating $API_APP image only (DATABASE_URL and Postgres unchanged)"
az containerapp update \
  -g "$RG" \
  -n "$API_APP" \
  --image "${ACR_LOGIN}/${API_IMAGE}:${TAG}" \
  -o none

echo "==> Updating $WEB_APP image only"
az containerapp update \
  -g "$RG" \
  -n "$WEB_APP" \
  --image "${ACR_LOGIN}/${WEB_IMAGE}:${TAG}" \
  -o none

API_FQDN=$(az containerapp show -g "$RG" -n "$API_APP" --query properties.configuration.ingress.fqdn -o tsv)
WEB_FQDN=$(az containerapp show -g "$RG" -n "$WEB_APP" --query properties.configuration.ingress.fqdn -o tsv)
echo ""
echo "New revision rolled out"
echo "App: https://$WEB_FQDN"
echo "API: https://$API_FQDN"
echo "PostgreSQL and DATABASE_URL were not changed."
