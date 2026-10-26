from rest_framework.authentication import SessionAuthentication

AUTH_HEADER = 'Session realm="api"'


class CsrfSessionAuthentication(SessionAuthentication):
    """Сессионная аутентификация Django с обязательной проверкой CSRF для небезопасных методов.

    `authenticate_header` нужен, чтобы DRF отвечал гостю 401 (а не 403) с заголовком WWW-Authenticate:
    401 — «нужен вход», 403 — «вход есть, прав нет» (ARCHITECTURE §2). Ошибка CSRF остаётся 403.
    """

    def authenticate_header(self, request):
        return AUTH_HEADER
