"""Расширения drf-spectacular для общих классов."""
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class CsrfSessionAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "apps.common.authentication.CsrfSessionAuthentication"
    name = "cookieAuth"

    def get_security_definition(self, auto_schema):
        return {"type": "apiKey", "in": "cookie", "name": "sessionid",
                "description": "Сессия Django; небезопасные методы требуют заголовок X-CSRFToken (GET /auth/csrf)."}
