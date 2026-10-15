#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077
mkdir -p backups
file="backups/inventory-$(date -u +%Y%m%dT%H%M%SZ).dump"
docker compose exec -T db pg_dump -U inventory -d inventory -Fc > "$file.tmp"
mv "$file.tmp" "$file"
sha256sum "$file" > "$file.sha256"
printf 'Backup created: %s\n' "$file"
