
import datetime
import importlib
import pickle
import signal
import sys
import threading

from django.db import (
    OperationalError,
    transaction,
)
from django.utils.timezone import now

from .conf import settings
from .cron import CronScheduler
from .models import (
    WAITING,
    RUNNING,
    DONE,
    ERROR,
    TaskQueue,
)


class TaskHandler(object):
    """The worker thread for handling callables."""

    def __init__(self):
        self.idle_time = settings.AUTOTASK_HANDLE_TASK_IDLE_TIME
        self.retry_delay = datetime.timedelta(
            seconds=settings.AUTOTASK_RETRY_DELAY)

    def __call__(self, exit_event):
        """Entry point for thread start and main loop for worker."""
        task = None
        while True:
            if task:
                self.handle_task(task)
            if exit_event.is_set():
                break
            task = self.get_next_task()
            if task:
                continue
            if exit_event.wait(timeout=self.idle_time):
                break

    def get_next_task(self):
        """
        Returns the next task from the queue on a first come first serve
        basis. Returns None if there is no pending task in the queue.
        """
        try:
            with transaction.atomic():
                qs = TaskQueue.objects.select_for_update()
                qs = qs.filter(status=WAITING, scheduled__lte=now())
                qs = qs.order_by('scheduled')
                task = qs.first()
                if task:
                    task.status = RUNNING
                    task.save()
        except OperationalError:
            # This exception is needed for SQLite3 which does not
            # support select_for_update().
            # In SQLite3 the first save-access wins and a concurrent
            # save-access will raise this exception.
            # In PostgeSQL the first select_for_update()-access wins
            # without raising an exception.
            # There may be another task waiting, so try it again.
            # (In the unlikely case the recursion limit is reached
            # the worker terminates but will restart from autotask.)
            return self.get_next_task()
        else:
            return task

    def handle_task(self, task):
        """
        Run a delayed or periodic task.
        """
        try:
            task = self._execute(task)
        except Exception as err:
            # catch everything, because it is unknown
            # what may had happen with the callable
            task.error = str(err)
            task.status = ERROR
            if task.is_periodic:
                task.scheduled = self.calculate_schedule(task)
            elif task.retries > 0:
                task.retries -= 1
                task.scheduled = now() + self.retry_delay
                task.status = WAITING
            else:
                # not scheduled again:
                task.expire = now() + task.ttl
        else:
            task.error = ''  # empty: no error
            if task.is_periodic:
                task.status = WAITING
                task.scheduled = self.calculate_schedule(task)
            else:
                task.status = DONE
                task.expire = now() + task.ttl
        task.save()

    def calculate_schedule(self, task):
        """
        Returns the next schedule for a repeating task.
        If task.timedelta is set it is a periodic task, otherwise it is
        a cron task and the next schedule as to be calculated after every
        run.
        """
        if task.function.endswith('_cron'):
            try:
                cron_data = pickle.loads(task.cron_data)
            except Exception as err:
                # don't break on any error.
                # report the error and stay in error-state
                # without a new schedule.
                task.error = str(err)
                task.status = ERROR
                return task.scheduled
            cs = CronScheduler(last_schedule=task.scheduled, **cron_data)
            next_schedule = cs.get_next_schedule()
        else:
            next_schedule = task.scheduled + task.timedelta
        return next_schedule

    def _execute(self, task):
        """
        Find callable, call it and store the result.
        """
        module = importlib.import_module(task.module)
        callable = getattr(module, task.function)
        args, kwargs = pickle.loads(task.arguments)
        result = callable(*args, **kwargs)
        task.result = pickle.dumps(result)
        return task


def run_queue_cleaner(exit_event=None, idle_time=None):
    """
    Clean tasks from the queue with the status DONE and without errors.
    """
    if not idle_time:
        idle_time = settings.AUTOTASK_CLEAN_INTERVALL
    while True:
        clean_queue()
        if exit_event.wait(timeout=idle_time):
            break
    sys.exit()


def clean_queue():
    """
    Cleanup no longer used task-entries in the database.
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


def start_workers():
    """
    Entry-Point to start the worker in a separate thread and the
    queue-cleaner in the main thread.
    """
    exit_event = threading.Event()
    thread = threading.Thread(target=TaskHandler(), args=(exit_event,))
    thread.start()
    handler = ShutdownHandler(exit_event)
    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGHUP, handler)
    run_queue_cleaner(exit_event)
