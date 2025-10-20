from django.apps import AppConfig


class EmpresaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'meuprojeto.empresa'
    verbose_name = 'Sistema de Gestão de Recursos Humanos'

    def ready(self):
        import meuprojeto.empresa.signals
