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
)


@pytest.mark.django_db
def test_set_supervisor_marker():
    # first call should return True
    assert set_supervisor_marker() is True
    # further calls should return False
    assert set_supervisor_marker() is False


@pytest.mark.django_db
def test_set_supervisor_marker_entry():
    assert TaskQueue.objects.all().count() == 0
    assert set_supervisor_marker() is True
    assert TaskQueue.objects.all().count() == 1


@pytest.mark.django_db
def test_start_supervisor():
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
def _test_queuecleaner():
    task = TaskQueue()
    task.status = DONE
    task.ttl = 0
    task.expire = now()
    task.save()
    assert TaskQueue.objects.all().count() == 1
    shutdown_handler = start_supervisor()
    time.sleep(0.1)  # give thread some time to run
    # still 1 because of supervisor marker entry
    assert TaskQueue.objects.all().count() == 1
    shutdown_handler()  # shut down supervisor-thread

