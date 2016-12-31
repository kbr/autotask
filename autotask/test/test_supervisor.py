import threading
import time
import pytest

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
