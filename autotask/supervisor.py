import subprocess
import threading

from django.db import (
    DEFAULT_DB_ALIAS,
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
from .shutdown import get_thread_shutdown_objects


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
        missing_processes = [process for process in self.processes
                             if process.poll() is not None]
        for process in missing_processes:
            self.processes.remove(process)
            self.processes.append(self.start_worker())

    def stop_workers(self):
        for process in self.processes:
            try:
                process.terminate()
            except OSError:
                # can happen with python 2.7 if the worker has been
                # restarted without unregistering the previous process
                pass
        self.processes = []
        self.delete_periodic_tasks()

    @transaction.atomic
    def delete_periodic_tasks(self):
        """
        Tasks are persistent in the db. Periodic tasks are read in at
        process start and will not expire. So they should get deleted
        here.
        """
        qs = TaskQueue.objects.filter(is_periodic=True)
        if qs.count():
            qs.delete()


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
        exit_thread()

    @staticmethod
    def clean_queue():
        """Removes no longer used task-entries from the database."""
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


def exit_thread():
    """
    Should get called from ending threads to close all
    database-connections in debug-mode. This is for running tests, so
    that the test-database gets unlocked and can be closed from pytest
    running in another thread.
    """
    if settings.DEBUG:
        connections.close_all()


def start_supervisor():
    """
    Start Supervisor if no other Supervisor is running.
    """
    if not set_supervisor_marker():
        # marker not set, supervisor may be running in another process
        return
    handler, exit_event = get_thread_shutdown_objects()
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
