
from django.apps import AppConfig

from .conf import settings


class AutotaskConfig(AppConfig):
    name = 'autotask'

    def ready(self):
        """
        starts a supervisor for the workers as long as no other
        supervisor is running. This is important in case the
        django-project runs with more than one process.
        """
        if settings.AUTOTASK_IS_ACTIVE:
            # import of .supervisor here, so tests can run
            # without raising an AppRegistryNotReady Exception
            from .supervisor import start_supervisor  # noqa
            start_supervisor()
