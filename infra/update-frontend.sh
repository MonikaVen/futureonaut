#!/usr/bin/env bash
# Rebuild and roll out ONLY the Futureonaut web (nginx) container.
# Does not touch PostgreSQL, the API container, or game files on the backend.
set -euo pipefail

RG="${RG:-rg-futureonaut}"
APP_NAME="${APP_NAME:-futureonaut-web}"
IMAGE_NAME="${IMAGE_NAME:-futureonaut-frontend}"
TAG="${TAG:-$(git -C "$(dirname "$0")/.." rev-parse --short HEAD)}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Using subscription $(az account show --query name -o tsv)"
echo "==> Resource group: $RG  app: $APP_NAME  tag: $TAG"

APP_JSON=$(az containerapp show -g "$RG" -n "$APP_NAME" -o json)
ACR_LOGIN=$(echo "$APP_JSON" | python3 -c "import json,sys,re
cfg=json.load(sys.stdin)
image=cfg['properties']['template']['containers'][0]['image']
print(image.split('/')[0])
")
if [[ -z "$ACR_LOGIN" || "$ACR_LOGIN" != *azurecr.io ]]; then
  echo "Could not infer ACR from $APP_NAME image" >&2
  exit 1
fi
ACR_NAME="${ACR_LOGIN%%.*}"

echo "==> Building frontend image in ACR $ACR_NAME (no backend rebuild)"
az acr build -r "$ACR_NAME" -t "${IMAGE_NAME}:${TAG}" -t "${IMAGE_NAME}:latest" "$ROOT/frontend"

echo "==> Updating $APP_NAME only (backend and database unchanged)"
az containerapp update \
  -g "$RG" \
  -n "$APP_NAME" \
  --image "${ACR_LOGIN}/${IMAGE_NAME}:${TAG}" \
  -o none

FQDN=$(az containerapp show -g "$RG" -n "$APP_NAME" --query properties.configuration.ingress.fqdn -o tsv)
echo ""
echo "Frontend revision rolled out"
echo "App: https://$FQDN"
echo "Backend and database were not updated."
