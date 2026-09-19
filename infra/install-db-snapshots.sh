#!/usr/bin/env bash
# Lock Azure Postgres to 7-day daily backups. On Burstable SKUs this is
# automated PITR (on-demand named snapshots are not supported).
set -euo pipefail

RG="${RG:-rg-futureonaut}"
PG_SERVER="${PG_SERVER:-fopg22613}"
KEEP_DAYS="${KEEP_DAYS:-7}"

ROOT="$(cd "$(dirname "$0")" && pwd)"
KEEP_DAYS="$KEEP_DAYS" "$ROOT/db-snapshot.sh"

echo "Daily database snapshots: Azure automated backups, retention ${KEEP_DAYS} days."
echo "Point-in-time restore is available back to backup.earliestRestoreDate."
