
import pytest

from autotask.supervisor import set_supervisor_marker


@pytest.mark.django_db
def test_set_supervisor_marker():
    # first call should return True
    assert set_supervisor_marker() is True
    # further calls should return False
    assert set_supervisor_marker() is False

