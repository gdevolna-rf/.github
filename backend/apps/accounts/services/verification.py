from apps.common.exceptions import Forbidden


def require_verified_email(account, action="этого действия"):
    """Отзывы и публикация профессиональных карточек требуют подтверждённого email (5.3)."""
    if not account.is_email_verified:
        raise Forbidden(f"Подтвердите email для {action}. Письмо со ссылкой можно отправить повторно в настройках.",
                        code="email_not_verified")
