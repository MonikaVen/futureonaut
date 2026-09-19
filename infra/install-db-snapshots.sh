#!/usr/bin/env bash
# Install a daily Container Apps Job that snapshots Postgres and keeps 7 days.
set -euo pipefail

RG="${RG:-rg-futureonaut}"
ENV_NAME="${ENV_NAME:-fo-cae}"
JOB_NAME="${JOB_NAME:-fo-pg-snapshot}"
IDENTITY_NAME="${IDENTITY_NAME:-fo-snapshot-id}"
PG_SERVER="${PG_SERVER:-fopg22613}"
LOCATION="${LOCATION:-northeurope}"

echo "==> User-assigned identity ${IDENTITY_NAME}"
az identity create -g "$RG" -n "$IDENTITY_NAME" -o none 2>/dev/null || true
IDENTITY_ID=$(az identity show -g "$RG" -n "$IDENTITY_NAME" --query id -o tsv)
PRINCIPAL_ID=$(az identity show -g "$RG" -n "$IDENTITY_NAME" --query principalId -o tsv)
CLIENT_ID=$(az identity show -g "$RG" -n "$IDENTITY_NAME" --query clientId -o tsv)

PG_ID=$(az postgres flexible-server show -g "$RG" -n "$PG_SERVER" --query id -o tsv)
echo "==> Role assignment on ${PG_SERVER}"
az role assignment create \
  --assignee-object-id "$PRINCIPAL_ID" \
  --assignee-principal-type ServicePrincipal \
  --role "Contributor" \
  --scope "$PG_ID" \
  -o none 2>/dev/null || true

# Job image is Azure CLI; the snapshot script is inlined so we do not need a custom image.
CRON="${CRON:-0 3 * * *}"
echo "==> Container Apps Job ${JOB_NAME} (${CRON} UTC)"
az containerapp job delete -g "$RG" -n "$JOB_NAME" --yes 2>/dev/null || true
az containerapp job create \
  -g "$RG" -n "$JOB_NAME" \
  --environment "$ENV_NAME" \
  --trigger-type Schedule \
  --cron-expression "$CRON" \
  --replica-timeout 1800 \
  --replica-retry-limit 1 \
  --image mcr.microsoft.com/azure-cli:2.67.0 \
  --cpu 0.25 --memory 0.5Gi \
  --mi-user-assigned "$IDENTITY_ID" \
  --command /bin/bash \
  --args -lc \
  "az login --identity --username ${CLIENT_ID} && \
   STAMP=\$(date -u +%Y%m%d) && \
   az postgres flexible-server update -g ${RG} -n ${PG_SERVER} --backup-retention 7 -o none && \
   az postgres flexible-server backup create -g ${RG} -n ${PG_SERVER} --backup-name fo-daily-\${STAMP} -o none || true && \
   az postgres flexible-server backup list -g ${RG} -n ${PG_SERVER} -o json | \
   python3 -c \"
import json,os,subprocess,sys
from datetime import datetime,timedelta,timezone
items=json.load(sys.stdin)
cutoff=datetime.now(timezone.utc)-timedelta(days=7)
for item in items:
    name=item.get('backupName') or item.get('name') or ''
    if not str(name).startswith('fo-daily-'):
        continue
    taken=item.get('completedTime') or item.get('startTime') or ''
    if not taken:
        continue
    when=datetime.fromisoformat(taken.replace('Z','+00:00'))
    if when<cutoff:
        subprocess.check_call(['az','postgres','flexible-server','backup','delete','-g','${RG}','-n','${PG_SERVER}','--backup-name',name,'--yes'])
\"
"
echo "Daily snapshots installed. Automated PITR retention is 7 days; named fo-daily-YYYYMMDD copies are pruned after 7 days."
