#!/usr/bin/env bash
# Keep a week of daily Azure Database for PostgreSQL backups.
# Burstable SKUs use automated PITR only (no customer on-demand snapshots).
set -euo pipefail

RG="${RG:-rg-futureonaut}"
PG_SERVER="${PG_SERVER:-fopg22613}"
KEEP_DAYS="${KEEP_DAYS:-7}"
STAMP="${STAMP:-$(date -u +%Y%m%d)}"
BACKUP_NAME="${BACKUP_NAME:-fo-daily-${STAMP}}"

echo "==> Setting automated backup retention to ${KEEP_DAYS} days"
az postgres flexible-server update \
  -g "$RG" -n "$PG_SERVER" \
  --backup-retention "$KEEP_DAYS" \
  -o none

TIER=$(az postgres flexible-server show -g "$RG" -n "$PG_SERVER" --query sku.tier -o tsv)
EARLIEST=$(az postgres flexible-server show -g "$RG" -n "$PG_SERVER" --query backup.earliestRestoreDate -o tsv)
echo "==> SKU tier: ${TIER}"
echo "==> Automated daily backups retained ${KEEP_DAYS} days (earliest restore: ${EARLIEST})"

if [[ "${TIER}" == "Burstable" ]]; then
  echo "==> On-demand named snapshots are not available on Burstable. Daily PITR copies are the snapshots."
  exit 0
fi

echo "==> Creating on-demand snapshot ${BACKUP_NAME}"
if az postgres flexible-server backup show \
  -g "$RG" -s "$PG_SERVER" -n "$BACKUP_NAME" &>/dev/null; then
  echo "Snapshot ${BACKUP_NAME} already exists"
else
  az postgres flexible-server backup create \
    -g "$RG" -s "$PG_SERVER" -n "$BACKUP_NAME" \
    -o none
fi

echo "==> Pruning on-demand snapshots older than ${KEEP_DAYS} days"
python3 - "$RG" "$PG_SERVER" "$KEEP_DAYS" <<'PY'
import json, subprocess, sys
from datetime import datetime, timedelta, timezone

rg, server, keep = sys.argv[1], sys.argv[2], int(sys.argv[3])
raw = subprocess.check_output(
    ["az", "postgres", "flexible-server", "backup", "list", "-g", rg, "-s", server, "-o", "json"],
    text=True,
)
backups = json.loads(raw)
cutoff = datetime.now(timezone.utc) - timedelta(days=keep)
for item in backups:
    name = item.get("backupName") or item.get("name") or ""
    if not str(name).startswith("fo-daily-"):
        continue
    taken = item.get("completedTime") or item.get("startTime") or item.get("backupStartedTime")
    if not taken:
        continue
    when = datetime.fromisoformat(taken.replace("Z", "+00:00"))
    if when < cutoff:
        print(f"deleting {name} ({taken})")
        subprocess.check_call(
            ["az", "postgres", "flexible-server", "backup", "delete",
             "-g", rg, "-s", server, "-n", name, "--yes"]
        )
PY

az postgres flexible-server backup list -g "$RG" -s "$PG_SERVER" \
  --query "[].{name:backupName,type:backupType,completed:completedTime}" -o table
