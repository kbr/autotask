import datetime
import random
import threading
import time

import pytest

from django.utils.timezone import now

from autotask.models import (
    DONE,
    TaskQueue,
)

from autotask.supervisor import (
    set_supervisor_marker,
    start_supervisor,
    Supervisor,
    QueueCleaner,
)


@pytest.mark.django_db
def test_set_supervisor_marker():
    # first call should return True
    assert set_supervisor_marker() is True
    # further calls should return False
    assert set_supervisor_marker() is False


@pytest.mark.django_db
def test_set_supervisor_marker_entry():
    """
    Test entry of supervisor-marker in the database.
    """
    assert TaskQueue.objects.all().count() == 0
    assert set_supervisor_marker() is True
    assert TaskQueue.objects.all().count() == 1


@pytest.mark.django_db
def test_start_supervisor():
    """
    Start Supervisor and count the number of threads: one for the
    Supervisor and one for the QueueCleaner. Test shutdown of both
    threads on calling the shutdown_handler.
    """
    ac = threading.active_count()
    shutdown_handler = start_supervisor()
    nc = threading.active_count()
    # +2: Supervisor and QueueCleaner threads
    assert nc == ac + 2
    shutdown_handler()  # shut down supervisor-thread
    time.sleep(0.1)  # give thread some time to terminate
    nc = threading.active_count()
    assert ac == nc


@pytest.mark.django_db
def test_supervisor_cleanup_periodic_tasks():
    """
    Periodic Tasks should be removed from the database when the
    supervisor shuts down. So there should be at least one Task in the
    db after starting the supervisor (the marker task) but there should
    be no task left in the db after the supervisor exits.
    """
    assert TaskQueue.objects.filter(is_periodic=True).count() == 0
    set_supervisor_marker()
    assert TaskQueue.objects.filter(is_periodic=True).count() == 1
    supervisor = Supervisor()
    supervisor.delete_periodic_tasks()
    time.sleep(0.1)  # give thread some time to terminate
    assert TaskQueue.objects.filter(is_periodic=True).count() == 0


@pytest.mark.django_db
def test_supervisor_terminatecleanup():
    """
    Periodic Tasks should be removed from the database when the
    supervisor shuts down. So there should be at least one Task in the
    db after starting the supervisor (the marker task) but there should
    be no task left in the db after the supervisor exits.
    """
    assert TaskQueue.objects.filter(is_periodic=True).count() == 0
    set_supervisor_marker()
    assert TaskQueue.objects.filter(is_periodic=True).count() == 1
    supervisor = Supervisor()
    supervisor.stop_workers()
    time.sleep(0.1)  # give thread some time to terminate
    assert TaskQueue.objects.filter(is_periodic=True).count() == 0


@pytest.mark.django_db
def test_start_workers():
    """
    Test successfull start of worker processes.
    """
    supervisor = Supervisor(workers=2)
    supervisor.start_workers()
    assert len(supervisor.processes) == 2
    # assume this works to not leave some running processes
    # after the pytest-run. There is a separate test for this.
    supervisor.stop_workers()


@pytest.mark.django_db
def test_stop_workers():
    """
    Test successfull stop of worker processes.
    """
    supervisor = Supervisor(workers=2)
    supervisor.start_workers()
    processes = supervisor.processes.copy()
    for process in processes:
        assert process.poll() is None  # up and running
    supervisor.stop_workers()
    for process in processes:
        assert process.poll() is not None  # down


@pytest.mark.django_db
def test_check_workers():
    """
    Test successfull restart worker processes.
    """
    def get_running_process_num(supervisor):
        return sum(process.poll() is None for process in supervisor.processes)

    supervisor = Supervisor(workers=2)
    supervisor.start_workers()
    assert get_running_process_num(supervisor) == 2
    # terminate a random process:
    process = random.choice(supervisor.processes)
    process.terminate()
    time.sleep(0.1)  # allow process some time to terminate
    assert get_running_process_num(supervisor) == 1
    supervisor.check_workers()
    assert get_running_process_num(supervisor) == 2
    # terminate all processes:
    for process in supervisor.processes:
        process.terminate()
    time.sleep(0.1)  # allow processes some time to terminate
    assert get_running_process_num(supervisor) == 0
    supervisor.check_workers()
    assert get_running_process_num(supervisor) == 2
    # clean up:
    supervisor.stop_workers()


@pytest.mark.django_db
def test_queuecleaner():
    """
    Runs periodically to remove expired tasks from the database.
    """
    assert TaskQueue.objects.filter(is_periodic=False).count() == 0
    set_supervisor_marker()
    assert TaskQueue.objects.all().count() == 1
    assert TaskQueue.objects.filter(is_periodic=False).count() == 0
    task = TaskQueue()
    task.is_periodic = False
    task.expire = now() + datetime.timedelta(minutes=5)
    task.save()
    assert TaskQueue.objects.filter(is_periodic=False).count() == 1
    qc = QueueCleaner()
    qc.clean_queue()
    assert TaskQueue.objects.filter(is_periodic=False).count() == 1
    task.expire = now()
    task.save()
    qc.clean_queue()
    assert TaskQueue.objects.filter(is_periodic=False).count() == 0
    assert TaskQueue.objects.all().count() == 1
