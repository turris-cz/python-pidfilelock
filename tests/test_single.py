"""Test locks from same process."""
import os

from pidfilelock import PIDFile, PIDLock, mklockdir, opportunistic_lock


def test_two_locks(tmp_path):
    """Test that one lock prevents locking to the other and other way around."""
    lockpath = tmp_path / "lock"
    lock1 = PIDLock(lockpath)
    lock2 = PIDLock(lockpath)
    assert lock1.lock(block=False)
    assert not lock2.lock(block=False)
    lock1.unlock()
    assert lock2.lock(block=False)
    assert not lock1.lock(block=False)
    lock2.unlock()
    assert not lockpath.exists()


def test_pid(tmp_path):
    """Test the client ability to get PID."""
    lockpath = tmp_path / "lock"
    lock = PIDLock(lockpath)
    file = PIDFile(lockpath)
    lock.lock()
    assert file.lock()
    assert file.pid == os.getpid()
    file.unlock()
    lock.unlock()
    assert not file.lock()
    assert not lockpath.exists()


def test_context(tmp_path):
    """Variant of test_pid that uses context manager."""
    lockpath = tmp_path / "lock"
    with PIDLock(lockpath) as lock:
        assert lock.is_locked
        with PIDFile(lockpath) as (file, locked):
            assert locked
            assert file.is_locked
            assert file.pid == os.getpid()
    assert not lockpath.exists()


def test_is_running(tmp_path):
    """Test the client ability to get PID."""
    lockpath = tmp_path / "lock"
    lock = PIDLock(lockpath)
    file = PIDFile(lockpath)
    assert not file.is_running  # No lock means that nothing is running
    lock.lock()
    assert file.is_running
    lock.unlock()
    assert not file.is_running


def test_opportunistic_lock(tmp_path):
    """Test our implementation of opportunity locking."""
    lockpath = tmp_path / "lock"
    with opportunistic_lock(lockpath) as lock:
        assert isinstance(lock, PIDLock)
        with opportunistic_lock(lockpath) as file:
            assert isinstance(file, PIDFile)
    with opportunistic_lock(lockpath) as lock:
        assert isinstance(lock, PIDLock)


def test_mklockdir(tmp_path):
    """Test that simple usage of mklockdir creates directory we can use for locks."""
    lockdir = tmp_path / "dir" / "subdir"
    assert not lockdir.exists()
    mklockdir(lockdir, parents=True)
    assert lockdir.exists()
    lockpath = lockdir / "lock"
    with PIDLock(lockpath) as _:
        assert lockpath.exists()
    assert not lockpath.exists()
    lockdir.rmdir()
    lockdir.parent.rmdir()
