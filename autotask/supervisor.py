
from django.db import (
    OperationalError,
    transaction,
)

from .models import (
    SUPERVISOR_ACTIVE,
    TaskQueue,
)

class Supervisor(object):
    pass


def start_supervisor():
    """
    """
    if not set_supervisor_marker():
        return



def set_supervisor_marker():
    """
    Checks whether a supervisor for a project is running.
    Returns True or False.
    Regardless of the processes started for a project, there should only one supervisor be active.
    """
    try:
        with transaction.atomic():
            qs = TaskQueue.objects.select_for_update()
            qs = qs.filter(status=SUPERVISOR_ACTIVE)
            if qs.count() > 0:
                return False
            marker = TaskQueue()
            marker.status = SUPERVISOR_ACTIVE  # ignored by TaskHandler
            marker.is_periodic = True  # but cleaned up at exit
            marker.save()
    except OperationalError:
        # This exception is needed for SQLite3 which does not
        # support select_for_update().
        # In SQLite3 the first save-access wins and a concurrent
        # save-access will raise this exception.
        # In this case another process may have already started
        # a supervisor.
        # A good reason not to use SQLite3 for projects running
        # more than one process.
        return False
    return True
