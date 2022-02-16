"""Test in subprocess after fork."""
import subprocess
import sys

import pytest

from pidfilelock import PIDFile, PIDLock

from . import barrier


def python_test_script(name, *args):
    return subprocess.Popen(
        [sys.executable, "-m", f"tests.{name}", *args],
        env={"PYTHONPATH": ":".join(sys.path)},
    )


@pytest.fixture(name="subproc_lock")
def fixture_subproc_lock(tmp_path):
    lockpath = tmp_path / "lock"
    with python_test_script("subprocess_lock", tmp_path) as subproc:
        b_up = barrier.WBarrier(tmp_path / "barrier-lock-up")
        b_sub = barrier.RBarrier(tmp_path / "barrier-lock")
        b_sub.wait()
        yield lockpath, b_up, b_sub, subproc
        subproc.kill()


def test_two_locks(subproc_lock):
    """Test two locks concurency."""
    lockpath, b_up, b_sub, _ = subproc_lock
    lock = PIDLock(lockpath)
    assert not lock.lock(block=False)
    b_up.invoke()
    b_sub.wait()
    assert lock.lock(block=False)


def test_pid(subproc_lock):
    """Test the PID file content."""
    lockpath, b_up, _, subproc = subproc_lock
    file = PIDFile(lockpath)
    assert subproc.pid == file.pid
    assert file.is_running
    b_up.invoke()


def test_file_block(subproc_lock):
    """Test the PIDFile can block the PIDLock unlock."""
    lockpath, b_up, _, subproc = subproc_lock
    file = PIDFile(lockpath)
    assert subproc.pid == file.pid
    assert file.is_running
    b_up.invoke()
