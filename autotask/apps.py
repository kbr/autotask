
import atexit
import os
import subprocess
import sys
import time
import threading

from django.apps import AppConfig
from django.conf import settings as django_settings

from .conf import settings


class ExitHandler(object):

    def __init__(self, process):
        self.process = process

    def __call__(self):
        try:
            self.process.terminate()
        except OSError:
            # can happen with python 2.7 on restarting the worker
            # without unregistering the previous process
            pass
        self.delete_periodic_tasks()

    def delete_periodic_tasks(self):
        """
        Tasks are persistent in the db. Periodic tasks are read in at
        process start and will not expire. So they should get deleted
        here.
        """
        from .models import TaskQueue  # noqa
        qs = TaskQueue.objects.filter(is_periodic=True)
        if qs.count():
            qs.delete()


class Supervisor(object):
    """
    Supervisor for the worker process.
    Starts and monitors the worker.
    """
    def __init__(self):
        self.exit_handler = None

    def __call__(self):
        process = self.start_worker()
        self.set_exit_handler(process)
        self.monitor_worker(process)

    def monitor_worker(self, process):
        while True:
            return_code = process.poll()
            if return_code:
                # bad things happend
                process = self.restart_process()
            else:
                time.sleep(settings.AUTOTASK_WORKER_MONITOR_INTERVALL)

    def restart_process(self):
        if sys.version_info.major >= 3:
            # does not work with python 2.7
            atexit.unregister(self.exit_handler)
        process = self.start_worker()
        self.set_exit_handler(process)
        return process

    def set_exit_handler(self, process):
        self.exit_handler = ExitHandler(process)
        atexit.register(self.exit_handler)

    def start_worker(self):
        os.environ.setdefault('DJANGO_AUTOTASK', 'true')
        process = subprocess.Popen(
            [settings.AUTOTASK_WORKER_EXECUTABLE, 'manage.py', 'run_autotask'],
            env=os.environ,
            cwd=django_settings.BASE_DIR)
        return process


class AutotaskConfig(AppConfig):
    name = 'autotask'
    is_called = False

    def ready(self):
        if not settings.AUTOTASK_IS_ACTIVE:
            return
        if self.is_called:
            return
        self.is_called = True
        if not os.environ.get('DJANGO_AUTOTASK'):
            self.start_supervisor()

    def start_supervisor(self):
        """
        Start supervisor as daemon thread so the supervisor-thread will
        not block on shut-down.
        """
        supervisor = Supervisor()
        thread = threading.Thread(target=supervisor)  #, daemon=True)
        thread.daemon = True  # for python 2.7 compatibility
        thread.start()
