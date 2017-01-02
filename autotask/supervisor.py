import os
import subprocess
import threading

from django.db import (
    OperationalError,
    transaction,
    connections,
)
from django.conf import settings as django_settings
from django.utils.timezone import now

from .conf import settings
from .models import (
    SUPERVISOR_ACTIVE,
    TaskQueue,
)
from .shutdown import get_shutdown_objects


class Supervisor(object):
    """
    Manages the workers: start, restart and stop.
    The supervisor runs in a separate thread.
    """
    def __init__(self, workers=settings.AUTOTASK_WORKERS):
        self.timeout = settings.AUTOTASK_WORKER_MONITOR_INTERVALL
        self.workers = workers  # number of workers to start
        self.processes = []

    def __call__(self, exit_event):
        self.start_workers()
        while True:
            if exit_event.wait(timeout=self.timeout):
                break
            self.check_workers()
        self.stop_workers()
        exit_thread()

    def start_workers(self):
        self.processes = [self.start_worker() for n in range(self.workers)]

    def start_worker(self):
        # use of Popen for Python 2 compatibility
        return subprocess.Popen([settings.AUTOTASK_WORKER_EXECUTABLE,
                                'manage.py', 'run_autotask'],
                                 cwd=django_settings.BASE_DIR)

    def check_workers(self):
        """
        Check whether all registered workers are up.
        Terminated processes (for whatever reason) are restarted.
        """
        missing_processes = [process for process in self.processes
                             if process.poll() is not None]
        for process in missing_processes:
            self.processes.remove(process)
            self.processes.append(self.start_worker())

    def stop_workers(self):
        """terminate all registered workers."""
        for process in self.processes:
            try:
                process.terminate()
            except OSError:
                # can happen with python 2.7 if the worker has been
                # restarted without unregistering the previous process
                pass
        self.processes = []


def clean_queue_periodically(exit_event):
    """Call clean_queue() periodically in a separate thread."""
    while True:
        if exit_event.wait(settings.AUTOTASK_CLEAN_INTERVALL):
            break
        clean_queue()
    exit_thread()


def clean_queue():
    """Removes no longer used task-entries from the database."""
    with transaction.atomic():
        qs = TaskQueue.objects.filter(is_periodic=False, expire__lt=now())
        if qs.count():
            qs.delete()


def delete_periodic_tasks():
    """
    Tasks are persistent in the db. Periodic tasks are read in at
    process start and will not expire. So they should get deleted
    here.
    """
    qs = TaskQueue.objects.filter(is_periodic=True)
    if qs.count():
        qs.delete()


def exit_thread():
    """
    Should get called from ending threads to close all
    database-connections in debug-mode. This is for running tests, so
    that the test-database gets unlocked and can be closed from pytest
    running in another thread.
    """
    if settings.DEBUG:
        connections.close_all()


def set_supervisor_marker():
    """
    Checks whether a supervisor for a project is running.
    Returns True or False.
    Regardless of the processes started for a project, there should only
    one supervisor be active.
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
            marker.module = __name__  # ident supervisor marker
            marker.function = str(os.getpid())  # id of supervisor process
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


def start_supervisor():
    """
    Start Supervisor if no other Supervisor is running.
    Returns None if no supervisor has started, otherwise returns a
    reference to the shutdown-handler. The latter should not get used by
    the application but is used for testing.
    """
    if not set_supervisor_marker():
        # marker already set, supervisor may be running in another process
        return None
    handler, exit_event = get_shutdown_objects()
    for service in (Supervisor(), clean_queue_periodically):
        thread = threading.Thread(target=service, args=(exit_event,))
        thread.start()
    # returning the ShutdownHandler can be ignored by the application
    # but is useful for testing
    return handler
