from django.apps import AppConfig


class FinappConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "finapp"

    def ready(self):
        import finapp.signals
