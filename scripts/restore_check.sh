#!/bin/sh
# Тренировочное восстановление (ATX-30): поднимает копию из дампа в отдельную БД и сверяет число строк
# в ключевых таблицах с рабочей базой. Рабочая БД не изменяется.
set -e
cd "$(dirname "$0")/.."
FILE=${1:-$(ls -t backups/*.dump 2>/dev/null | head -1)}
[ -n "$FILE" ] || { echo "нет дампа: сначала scripts/backup.sh"; exit 1; }
TARGET=restore_check
echo "restore $FILE -> $TARGET"
docker compose exec -T postgres sh -c "dropdb -U \"\$POSTGRES_USER\" --if-exists $TARGET && createdb -U \"\$POSTGRES_USER\" $TARGET"
docker compose exec -T postgres sh -c "pg_restore -U \"\$POSTGRES_USER\" -d $TARGET --no-owner" < "$FILE"
TABLES="accounts_account spots_spot organizations_organization boards_boardmodel commerce_inquiry commerce_booking messaging_message trust_review trust_auditevent"
FAIL=0
for t in $TABLES; do
  SRC=$(docker compose exec -T postgres sh -c "psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -tAc 'select count(*) from $t'")
  DST=$(docker compose exec -T postgres sh -c "psql -U \"\$POSTGRES_USER\" -d $TARGET -tAc 'select count(*) from $t'")
  STATUS=ok; [ "$SRC" = "$DST" ] || { STATUS="MISMATCH"; FAIL=1; }
  printf "%-32s live=%-6s restored=%-6s %s\n" "$t" "$SRC" "$DST" "$STATUS"
done
docker compose exec -T postgres sh -c "dropdb -U \"\$POSTGRES_USER\" $TARGET"
[ $FAIL = 0 ] && echo "restore check: OK" || { echo "restore check: FAILED"; exit 1; }
