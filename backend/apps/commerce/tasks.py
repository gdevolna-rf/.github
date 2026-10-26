"""Периодические задачи commerce (ARCHITECTURE §5)."""
from celery import shared_task


@shared_task(name="commerce.expire_stale_booking_requests")
def expire_stale_booking_requests():
    """Запросы старше BOOKING_REQUEST_TTL_HOURS или с наступившим началом → cancelled (side=system) + уведомления."""
    from apps.commerce.services.bookings import expire_stale_requests

    return expire_stale_requests()


@shared_task(name="commerce.mark_overdue_rentals")
def mark_overdue_rentals():
    """Выданная аренда после ends_at → is_overdue + однократное уведомление обеим сторонам."""
    from apps.commerce.services.bookings import mark_overdue_rentals as run

    return run()
