from django.apps import AppConfig


class InventoryConfig(AppConfig):
    name = "apps.inventory"
    label = "inventory"
    verbose_name = "Инвентарь и аренда"

    def ready(self):
        from apps.inventory import signals  # noqa: F401
