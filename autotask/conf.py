
from django.conf import settings as django_settings


class Settings(object):
    """
    Define all autotask-settings in a common place
    as attributes of a settings-object.
    """

    def __init__(self):
        self._set_defaults()
        self._get_overrides()

    def _set_defaults(self):
        """
        Set some useable defaults.
        """
        self.AUTOTASK_CLEAN_INTERVALL = 600
        self.AUTOTASK_HANDLE_TASK_IDLE_TIME = 10
        self.AUTOTASK_IS_ACTIVE = False
        self.AUTOTASK_WORKER_EXECUTABLE = 'python'
        self.AUTOTASK_WORKER_MONITOR_INTERVALL = 5
        self.AUTOTASK_RETRY_DELAY = 2

    def _get_overrides(self):
        """
        Read optional overridden values from the django settings
        """
        for attr in dir(self):
            if attr.isupper():
                try:
                    value = getattr(django_settings, attr)
                except AttributeError:
                    continue
                setattr(self, attr, value)


settings = Settings()
