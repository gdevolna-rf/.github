from celery import shared_task


@shared_task(name="mediafiles.process_media", bind=True, autoretry_for=(ConnectionError, TimeoutError),
             retry_backoff=True, max_retries=5)
def process_media(self, asset_id):
    """Проверка сигнатуры, очистка EXIF, миниатюра → ready / rejected."""
    from botocore.exceptions import BotoCoreError, ClientError

    from apps.mediafiles.services.processing import process_media as run

    try:
        return run(asset_id)
    except (BotoCoreError, ClientError) as exc:  # хранилище временно недоступно
        raise self.retry(exc=exc)


@shared_task(name="mediafiles.cleanup_expired_uploads")
def cleanup_expired_uploads():
    """Каждый час: pending-загрузки с истёкшей ссылкой удаляются, зависшие processing перезапускаются."""
    from apps.mediafiles.services.uploads import cleanup_expired_uploads as run

    return run()
