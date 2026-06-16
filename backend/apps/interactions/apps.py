from django.apps import AppConfig


class InteractiosnConfig(AppConfig):
    name = 'apps.interactions'

    def ready(self):
        import apps.interactions.signals

