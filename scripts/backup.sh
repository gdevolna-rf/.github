#!/bin/sh
# Резервная копия PostgreSQL в ./backups (формат custom, для pg_restore).
set -e
cd "$(dirname "$0")/.."
STAMP=$(date +%Y%m%d-%H%M%S)
FILE="backups/gdevolna-$STAMP.dump"
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$FILE"
echo "backup: $FILE ($(du -h "$FILE" | cut -f1))"
