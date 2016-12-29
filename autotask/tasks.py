"""
Function-Decorators for async task-execution by a worker.
"""

import importlib
import pickle
from datetime import timedelta

from django.utils.timezone import now

from .conf import settings
from .cron import CronScheduler
from .models import (
    WAITING,  # noqa
    RUNNING,  # noqa
    DONE,
    ERROR,
    TaskQueue,
)


class DelayedTask(object):
    """
    Gives access to a delayed function.
    """

    def __init__(self, pk):
        # pk of TaskQueue item in db
        self.pk = pk

    def _get_task(self):
        try:
            return TaskQueue.objects.get(pk=self.pk)
        except TaskQueue.DoesNotExist:
            return None

    @property
    def ready(self):
        """
        Returns True, False or None.
        In case of None the task is lost and no informations are
        available.
        """
        task = self._get_task()
        if task and not task.is_periodic:
            return task.status == DONE or task.status == ERROR
        return None

    @property
    def status(self):
        """
        Returns the processing status.
        """
        task = self._get_task()
        if task:
            return task.status
        return None

    @property
    def result(self):
        """
        Returns the result of the task.
        """
        task = self._get_task()
        if task:
            try:
                return pickle.loads(task.result)
            except EOFError:
                # if task.result is None this exception will raised
                pass
        return None

    @property
    def error_message(self):
        """
        Returns the error-message as string. If no error has occured
        returns an empty string.
        """
        task = self._get_task()
        if task:
            return task.error_message
        return ''


class DecoratorBase(object):
    """
    Common functionality for a decorator accepting arguments.
    """

    def __call__(self, function):
        """bind function-label to self.wrapper"""
        if not settings.AUTOTASK_IS_ACTIVE:
            # don't wrapp on inactive autotask
            return function
        self.module_name = function.__module__
        module = importlib.import_module(function.__module__)
        self.function_name = self.template.format(function.__name__)
        setattr(module, self.function_name, function)
        if not self.function_name.endswith('_delayed'):
            # a periodic task will never get called from the application
            # so the wrapper has to be called here:
            self.wrapper()
        return self.wrapper

    def wrapper(self, *args, **kwargs):
        """
        Gets called instead of function. Adds a TaskQueue item for the
        wrapped function and return a DelayedTask objects for accessing
        status-informations and optional results.
        """
        tq = TaskQueue()
        tq.arguments = pickle.dumps((args, kwargs))
        tq.module = self.module_name
        tq.function = self.function_name
        tq = self.configure(tq)
        if tq.is_periodic:
            if self.is_registered(tq):
                return None
        tq.save()
        dt = DelayedTask(tq.pk)
        return dt

    def is_registered(self, tq):
        """
        Returns a boolean whether a task is allready saved in the
        database. This is to prevent periodic tasks registered more than
        once at startup what will happen if the django-project is
        running with more than one process.
        """
        try:
            TaskQueue.objects.get(
                module=tq.module,
                function=tq.function,
                is_periodic=tq.is_periodic)
        except TaskQueue.DoesNotExist:
            return False
        return True


class delayed_task(DecoratorBase):  # noqa
    """
    Decorator to wrap a function for delayed execution by a separate
    worker process.
    :delay: worker waits n seconds before processing
    :retries: on error try to rerun the tasks n times
    :ttl: time to live: after processing the task will stay at least n
    seconds in the database i.e. for accessing the result.

        @delayed_task(optional arguments)
        def long_runner(*args, **kwargs)
        ...
        dt = long_runner()

    The returned object dt is of type DelayedTask
    """
    def __init__(self, delay=0, retries=0, ttl=300):
        self.ttl = timedelta(seconds=ttl)
        self.delay = timedelta(seconds=delay)
        self.retries = retries
        self.template = '{}_delayed'

    def configure(self, tq):
        tq.scheduled = now() + self.delay
        tq.retries = self.retries
        tq.ttl = self.ttl
        tq.is_periodic = False
        return tq


class periodic_task(DecoratorBase):  # noqa
    """
    Decorator for a periodic task running every given number of seconds
    Returns a DelayedTask object. Usage:

        @periodic_task()
        def some_function():
            ...

    Default period is 3600 seconds. If start_now is True the task will
    run as soon as possible and then periodically. Id start_now is False
    the task will be delayed by the given period before running
    periodically.
    """
    def __init__(self, seconds=3600, start_now=False):
        self.timedelta = timedelta(seconds=seconds)
        self.delay = timedelta() if start_now else self.timedelta
        self.template = '{}_periodic'

    def configure(self, tq):
        tq.scheduled = now() + self.delay
        tq.timedelta = self.timedelta
        tq.is_periodic = True
        return tq


class cron_task(DecoratorBase):  # noqa
    """
    Decorator for a periodic task running by a crontab-like schedule:

        @cron_task(optional arguments)
        def the_task()

    The arguments are:

    minutes: list of integers in the range 0-59 or None. [5, 15] will
    run 5 and 15 minutes after full hour. If None the task will run
    every minute.

    hours: list of integers in the range 0-23 or None. [5, 15] will run
    at 5 a.m. and 3 p.m. If None the task will run every hour.

    dow: list of integers in the range 0-6 or None. Describes the days
    of week when a task should run. Monday is 0 and Sunday is 6. [2, 4]
    will run every Wednesday and Friday. If None the task will run every
    day.

    month: list of integers in the range 1-12 or None. Describes the
    month of a year when a task should run. [4, 7] will run in April and
    July. If None the task will run every month.

    dom: list of integers in the range 1-31 or None. Describes the days
    of a month when a task should run. [4, 15] will run at the 4th and
    15th of every month. If None the task will run every day.


    Some examples:

    @cron_task(minutes=[15, 30], hours=[7, 20])
    Runs every day at 7:15, 7:30, 20:15, 20:30

    @cron_task(minutes=[30], hours=[7], dow=[0, 2])
    Runs every Monday and Wednesday at 7:30

    @cron_task(minutes=[30], hours=[7], dow=[0, 2], month=[4, 7])
    Runs every Monday and Wednesday at 7:30 in April and July

    @cron_task(minutes=[30], hours=[7], dom=[1, 15])
    Runs every 1st and 15th of a month at 7:30

    @cron_task(minutes=[30], hours=[7], dow=[0], dom=[1, 15])
    Runs every 1st and 15th of a month and at Mondays at 7:30

    @cron_task(minutes=[30], hours=[7], dow=[0], month=[4], dom=[1, 15])
    Runs at 1st and 15th and at Mondays at 7:30 but only in April

    If all arguments are None the task will run every minute, the same
    as @periodic_task(seconds=60).

    Instead of the separate arguments also a crontab with five patterns
    can be given (pattern order: minutes, hours, day of month, months,
    day of week):
    * * * * *       runs every minute (same as @periodic_task(seconds=60))
    30 7 * * 0,2    runs at 7:30 every Monday and Wednesday.

    """
    def __init__(self, minutes=None, hours=None,
                 dow=None, months=None, dom=None,
                 crontab=None):
        self.template = '{}_cron'
        self.cron_data = {
            'minutes': minutes,
            'hours': hours,
            'dow': dow,
            'months': months,
            'dom': dom,
            'crontab': crontab
        }

    def configure(self, tq):
        cs = CronScheduler(**self.cron_data)
        tq.scheduled = cs.get_next_schedule()
        tq.cron_data = pickle.dumps(self.cron_data)
        tq.is_periodic = True
        return tq
