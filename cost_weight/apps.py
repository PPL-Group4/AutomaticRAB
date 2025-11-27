from django.apps import AppConfig


class CostWeightConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cost_weight'

    def ready(self):
        pass
