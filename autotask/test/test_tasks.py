
import time
import pytest

from autotask.conf import settings
settings.AUTOTASK_IS_ACTIVE = True

from autotask.models import (
    WAITING,
    RUNNING,
    DONE,
    ERROR,
    TaskQueue,
)
from autotask.supervisor import clean_queue
from autotask.tasks import (
    DelayedTask,
    delayed_task,
    periodic_task,
)
from autotask.worker import (
    TaskHandler,
)


# test functions
def add(a, b):
    return a + b

@delayed_task()
def add2(a, b):
    return a + b

@delayed_task(retries=1)
def add3(a, b):
    return a + b

@delayed_task(ttl=0.1)
def add4(a, b):
    return a + b

@delayed_task()
def mult(a, b):
    return a * b

@delayed_task(delay=0.01)
def mult2(a, b):
    return a * b


@pytest.mark.django_db
class TestAutotask(object):
    @pytest.fixture(autouse=True)
    def set_up(self):
        pass

    def test_delayed_task_01(self):
        """Test whether tasks get stored."""
        n = TaskQueue.objects.all().count()
        assert 0 == n
        dt = delayed_task()
        f = dt(add)
        f(2, 2)
        n = TaskQueue.objects.all().count()
        assert 1 == n

    def test_delayed_task_02(self):
        """Test for return object."""
        dt = delayed_task()
        f = dt(add)
        r = f(2, 2)
        assert True is isinstance(r, DelayedTask)

    def test_decorator_01(self):
        """Test for return object."""
        r = add2(2, 2)
        assert True is isinstance(r, DelayedTask)

    def test_decorator_02(self):
        """Test for return attributes."""
        r = add2(2, 2)
        assert r.ready is False
        assert r.status == WAITING

    def test_taskhandler_01(self):
        """should return None if no task found."""
        th = TaskHandler()
        assert th.get_next_task() is None

    def test_taskhandler_02(self):
        """Test whether is an entry in the database."""
        n = TaskQueue.objects.all().count()
        assert n == 0
        r = add2(2, 2)
        n = TaskQueue.objects.all().count()
        assert n == 1

    def test_taskhandler_03(self):
        """Test for accessing this entry."""
        r = add2(2, 2)
        th = TaskHandler()
        task = th.get_next_task()
        assert task.status == RUNNING

    def test_taskhandler_04(self):
        """Test for accessing the first entry."""
        r = add2(2, 2)
        p = mult(2, 2)
        th = TaskHandler()
        task = th.get_next_task()
        assert task.function == 'add2_delayed'

    @pytest.mark.parametrize(
        'a, b, result, status, ready', [
            (2, 3, 5, DONE, True),
            (2, "a", None, ERROR, True),
            ('a', 'b', 'ab', DONE, True),
        ])
    def test_taskhandler_05(self, a, b, result, status, ready):
        """test error handling."""
        r = add2(a, b)
        th = TaskHandler()
        task = th.get_next_task()
        th.handle_task(task)
        assert task.status == status
        assert r.status == status
        assert r.result == result
        assert r.ready is True

    @pytest.mark.parametrize(
        'delay, ready', [
            (0, False),
            (0.012, True),
        ])
    def test_taskhandler_06(self, delay, ready):
        """test delay."""
        th = TaskHandler()
        r = mult2(2, 2)
        time.sleep(delay)
        task = th.get_next_task()
        if task:
            th.handle_task(task)
        assert r.ready is ready

    def test_taskhandler_07(self):
        """test retries."""
        r = add3(2, 'c')
        th = TaskHandler()
        task = th.get_next_task()
        th.handle_task(task)
        assert r.status == WAITING
        # should be false because the task is rescheduled
        assert r.ready is False
        time.sleep(1)
        task = th.get_next_task()
        # should be None becaus schedule delay is 1 sec.
        assert task is None
        time.sleep(1.5)
        task = th.get_next_task()
        assert task is not None
        th.handle_task(task)
        # now status should be ERROR and task is done
        assert r.status == ERROR
        assert r.ready is True

    @pytest.mark.parametrize(
        'ttl, result', [
            (0, 5),
            (0.05, 5),
            (0.15, None),
        ])
    def test_taskhandler_08(self, ttl, result):
        """test ttl."""
        r = add4(2, 3)
        th = TaskHandler()
        task = th.get_next_task()
        th.handle_task(task)
        time.sleep(ttl)
        clean_queue()
        assert r.result == result

    def test_periodic_task01(self):

        @periodic_task(seconds=0.02, start_now=True)
        def gettime():
            return time.time()

        _ = gettime()
        th = TaskHandler()
        task = th.get_next_task()
        assert task is not None

    def test_periodic_task02(self):

        @periodic_task(seconds=0.02, start_now=False)
        def gettime():
            return time.time()

        _ = gettime()
        th = TaskHandler()
        task = th.get_next_task()
        assert task is None
        # wait shorter than timedelta and try again.
        # result should not change.
        time.sleep(0.01)
        task = th.get_next_task()
        assert task is None
        # now the task should be available.
        time.sleep(0.02)
        task = th.get_next_task()
        assert task is not None
