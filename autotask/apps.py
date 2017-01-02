import atexit

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
            from .supervisor import (  # noqa
                start_supervisor,
                delete_periodic_tasks
            )
            start_supervisor()
            # fallback in case the supervisor-thread terminates without
            # a proper cleanup.
            # Also abandoned supervisor marker preventing autotask to start
            # can be removed this way.
            # (remove marker manually or start and restart django)
            atexit.register(delete_periodic_tasks)
