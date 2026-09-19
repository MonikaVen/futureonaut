#!/usr/bin/env bash
# Create a named daily snapshot of Azure Database for PostgreSQL.
# Keeps on-demand snapshots for 7 days. Automated PITR retention is also 7 days.
set -euo pipefail

RG="${RG:-rg-futureonaut}"
PG_SERVER="${PG_SERVER:-fopg22613}"
KEEP_DAYS="${KEEP_DAYS:-7}"
STAMP="${STAMP:-$(date -u +%Y%m%d)}"
BACKUP_NAME="${BACKUP_NAME:-fo-daily-${STAMP}}"

echo "==> Ensuring automated backup retention is ${KEEP_DAYS} days"
az postgres flexible-server update \
  -g "$RG" -n "$PG_SERVER" \
  --backup-retention "$KEEP_DAYS" \
  -o none

echo "==> Creating on-demand snapshot ${BACKUP_NAME}"
if az postgres flexible-server backup show \
  -g "$RG" -n "$PG_SERVER" --backup-name "$BACKUP_NAME" &>/dev/null; then
  echo "Snapshot ${BACKUP_NAME} already exists"
else
  az postgres flexible-server backup create \
    -g "$RG" -n "$PG_SERVER" \
    --backup-name "$BACKUP_NAME" \
    -o none
fi

echo "==> Pruning on-demand snapshots older than ${KEEP_DAYS} days"
python3 - "$RG" "$PG_SERVER" "$KEEP_DAYS" <<'PY'
import json, subprocess, sys
from datetime import datetime, timedelta, timezone

rg, server, keep = sys.argv[1], sys.argv[2], int(sys.argv[3])
raw = subprocess.check_output(
    ["az", "postgres", "flexible-server", "backup", "list", "-g", rg, "-n", server, "-o", "json"],
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
             "-g", rg, "-n", server, "--backup-name", name, "--yes"]
        )
PY

echo "==> Current snapshots"
az postgres flexible-server backup list -g "$RG" -n "$PG_SERVER" \
  --query "[].{name:backupName,type:backupType,completed:completedTime}" -o table
