#!/bin/sh
set -e

wait_for_db() {
  until pg_isready -h "$POSTGRES_HOST" -p "${POSTGRES_PORT:-5432}" -U "$POSTGRES_USER" >/dev/null 2>&1; do
    echo "waiting for postgres..."; sleep 1
  done
}

case "$1" in
  web)
    wait_for_db
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput >/dev/null
    python manage.py init_storage
    python manage.py setup_periodic_tasks
    # Демо-данные — только dev/staging: в production посев не выполняется даже при SEED_DEMO=1.
    if [ "${SEED_DEMO:-0}" = "1" ] && [ "${APP_ENV:-dev}" != "prod" ]; then python manage.py seed_demo --if-empty; fi
    exec daphne -b 0.0.0.0 -p 8000 --proxy-headers config.asgi:application
    ;;
  worker)
    wait_for_db
    exec celery -A config worker -l info --concurrency=2
    ;;
  beat)
    wait_for_db
    exec celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    ;;
  *)
    exec "$@"
    ;;
esac
