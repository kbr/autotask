import signal
import threading

from django.db import (
    OperationalError,
    transaction,
)
from django.utils.timezone import now

from .conf import settings

from .models import (
    SUPERVISOR_ACTIVE,
    TaskQueue,
)


class Supervisor(object):
    """
    Manages the workers: start, restart and stop.
    Runs in a separate thread.
    """
    def __init__(self):
        self.timeout = settings.AUTOTASK_WORKER_MONITOR_INTERVALL

    def __call__(self, exit_event):
        while True:
            if exit_event.wait(timeout=self.timeout):
                break


class QueueCleaner(object):
    """
    Removes outdated TaskQueue-Objects from the database.
    Runs in a separate thread.
    """
    def __init__(self):
        self.timeout = settings.AUTOTASK_CLEAN_INTERVALL

    def __call__(self, exit_event):
        while True:
            if exit_event.wait(timeout=self.timeout):
                break
            self.clean_queue()

    @staticmethod
    def clean_queue():
        """
        Removes no longer used task-entries from the database.
        """
        with transaction.atomic():
            qs = TaskQueue.objects.filter(is_periodic=False, expire__lt=now())
            if qs.count():
                qs.delete()


class ShutdownHandler(object):
    """
    Sets the event for terminating the threads.
    """
    def __init__(self, exit_event):
        self.exit_event = exit_event

    def __call__(self, *args, **kwargs):
        self.exit_event.set()


def start_supervisor():
    """
    Start Supervisor if no other Supervisor is running.
    """
    if not set_supervisor_marker():
        # marker not set, supervisor may be running in another process
        return
    exit_event = threading.Event()
    handler = ShutdownHandler(exit_event)
    # handler should react on SIGINT, SIGHUP:
    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGHUP, handler)
    # start Supervisor:
    thread = threading.Thread(target=Supervisor(), args=(exit_event,))
    thread.start()
    # start QueueCleaner:
    thread = threading.Thread(target=QueueCleaner(), args=(exit_event,))
    thread.start()
    # returning the ShutdownHandler can be ignored by the application
    # but is useful for testing
    return handler


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
