#!/usr/bin/env bash
set -euo pipefail

LOCATION="${LOCATION:-westeurope}"
RG="${RG:-rg-futureonaut}"
ACR_NAME="${ACR_NAME:-foacr$RANDOM}"
ENV_NAME="${ENV_NAME:-fo-cae}"
PG_SERVER="${PG_SERVER:-fopg$RANDOM}"
PG_ADMIN="foadmin"
PG_PASSWORD="${PG_PASSWORD:-Fo$(openssl rand -hex 10)Aa1}"
JWT_SECRET="${JWT_SECRET:-$(openssl rand -hex 32)}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@example.com}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin12345}"
OPENAI_API_KEY="${OPENAI_API_KEY:-}"
LAW_NAME="${LAW_NAME:-fo-logs}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
ACR_NAME=$(echo "$ACR_NAME" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9' | cut -c1-40)
PG_SERVER=$(echo "$PG_SERVER" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9' | cut -c1-40)

echo "==> Using subscription $(az account show --query name -o tsv)"
az group create -n "$RG" -l "$LOCATION" -o none

echo "==> Log Analytics + Container Apps Environment"
az monitor log-analytics workspace create -g "$RG" -n "$LAW_NAME" -l "$LOCATION" -o none 2>/dev/null || true
LAW_ID=$(az monitor log-analytics workspace show -g "$RG" -n "$LAW_NAME" --query customerId -o tsv)
LAW_KEY=$(az monitor log-analytics workspace get-shared-keys -g "$RG" -n "$LAW_NAME" --query primarySharedKey -o tsv)
az containerapp env create -g "$RG" -n "$ENV_NAME" -l "$LOCATION" \
  --logs-workspace-id "$LAW_ID" --logs-workspace-key "$LAW_KEY" -o none 2>/dev/null || true

echo "==> PostgreSQL Flexible Server"
az postgres flexible-server create \
  -g "$RG" -n "$PG_SERVER" -l "$LOCATION" \
  --admin-user "$PG_ADMIN" --admin-password "$PG_PASSWORD" \
  --sku-name Standard_B1ms --tier Burstable --storage-size 32 \
  --version 16 --public-access 0.0.0.0-255.255.255.255 \
  --yes -o none
az postgres flexible-server db create -g "$RG" -s "$PG_SERVER" -d futureonaut -o none
PG_HOST=$(az postgres flexible-server show -g "$RG" -n "$PG_SERVER" --query fullyQualifiedDomainName -o tsv)
PG_PASSWORD_ENC=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1], safe=''))" "$PG_PASSWORD")
DATABASE_URL="postgresql+psycopg://${PG_ADMIN}:${PG_PASSWORD_ENC}@${PG_HOST}:5432/futureonaut?sslmode=require"

echo "==> ACR + images"
az acr create -g "$RG" -n "$ACR_NAME" --sku Basic --admin-enabled true -o none
az acr build -r "$ACR_NAME" -t futureonaut-backend:latest ./backend
az acr build -r "$ACR_NAME" -t futureonaut-frontend:latest ./frontend
ACR_LOGIN=$(az acr show -n "$ACR_NAME" --query loginServer -o tsv)
ACR_USER=$(az acr credential show -n "$ACR_NAME" --query username -o tsv)
ACR_PASS=$(az acr credential show -n "$ACR_NAME" --query passwords[0].value -o tsv)

echo "==> Backend app"
az containerapp create \
  -g "$RG" -n futureonaut-api \
  --environment "$ENV_NAME" \
  --image "$ACR_LOGIN/futureonaut-backend:latest" \
  --registry-server "$ACR_LOGIN" \
  --registry-username "$ACR_USER" \
  --registry-password "$ACR_PASS" \
  --cpu 0.5 --memory 1.0Gi \
  --min-replicas 1 --max-replicas 2 \
  --ingress external --target-port 8000 \
  --env-vars \
    "DATABASE_URL=$DATABASE_URL" \
    "JWT_SECRET=$JWT_SECRET" \
    "ADMIN_EMAIL=$ADMIN_EMAIL" \
    "ADMIN_PASSWORD=$ADMIN_PASSWORD" \
    "GAMES_DIR=/data/games" \
    "OPENAI_API_KEY=$OPENAI_API_KEY" \
    "CORS_ORIGINS=*" \
  -o none

API_FQDN=$(az containerapp show -g "$RG" -n futureonaut-api --query properties.configuration.ingress.fqdn -o tsv)
API_URL="https://$API_FQDN"

echo "==> Frontend app"
az containerapp create \
  -g "$RG" -n futureonaut-web \
  --environment "$ENV_NAME" \
  --image "$ACR_LOGIN/futureonaut-frontend:latest" \
  --registry-server "$ACR_LOGIN" \
  --registry-username "$ACR_USER" \
  --registry-password "$ACR_PASS" \
  --cpu 0.25 --memory 0.5Gi \
  --min-replicas 1 --max-replicas 2 \
  --ingress external --target-port 80 \
  --env-vars "BACKEND_UPSTREAM=$API_URL" \
  -o none

WEB_FQDN=$(az containerapp show -g "$RG" -n futureonaut-web --query properties.configuration.ingress.fqdn -o tsv)
WEB_URL="https://$WEB_FQDN"

az containerapp update -g "$RG" -n futureonaut-api \
  --set-env-vars "CORS_ORIGINS=$WEB_URL" "PUBLIC_BASE_URL=${PUBLIC_BASE_URL:-$WEB_URL}" -o none

cat > "$ROOT/azure-deploy-out.env" <<EOF
RG=$RG
WEB_URL=$WEB_URL
API_URL=$API_URL
ADMIN_EMAIL=$ADMIN_EMAIL
ADMIN_PASSWORD=$ADMIN_PASSWORD
PG_SERVER=$PG_SERVER
ACR_NAME=$ACR_NAME
EOF

echo ""
echo "============================================"
echo "Futureonaut deployed"
echo "App:   $WEB_URL"
echo "API:   $API_URL"
echo "Admin: $ADMIN_EMAIL / $ADMIN_PASSWORD"
echo "============================================"
