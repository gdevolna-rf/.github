from django.apps import AppConfig


class SpotsConfig(AppConfig):
    name = "apps.spots"
    label = "spots"
    verbose_name = "Споты"

    def ready(self):
        from apps.spots import signals  # noqa: F401
