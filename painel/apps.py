from django.apps import AppConfig


class PainelConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "painel"
    verbose_name = "Ocorrências"

    def ready(self):
        from painel import signals  # noqa: F401
