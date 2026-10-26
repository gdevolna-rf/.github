from django.apps import AppConfig


class CommonConfig(AppConfig):
    name = "apps.common"
    label = "common"
    verbose_name = "Общее"

    def ready(self):
        from apps.common import schema  # noqa: F401  регистрация OpenAPI-расширений
