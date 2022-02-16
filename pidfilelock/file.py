"""The implementation of client class to query and use pidfilelock."""
import fcntl
import logging
import os

from ._base import PIDBase as _PIDBase
from .tools import pid_is_running

logger = logging.getLogger(__name__)


class PIDFile(_PIDBase):
    """The class that won't create the lock but allows reading it."""

    def lock(self) -> bool:
        """Lock the PID file for reading.

        This is required to be always performed before the PID file is read. This has two effects. It ensures that file
        content is consistent and thus correct. It also allows process shutdown to be postponed if PIDLock unlocks with
        enabled blocking.

        Returns True if lock was succesfull or False otherwise.
        """
        assert self.fileno is None, "Lock is already obtained."
        while True:
            try:
                fileno = os.open(self.path, os.O_RDONLY)
            except FileNotFoundError:
                return False  # No file means no lock
            fcntl.flock(fileno, fcntl.LOCK_SH)
            if self.path.stat().st_ino != os.fstat(fileno).st_ino:
                logger.debug(
                    "The PID lock file was removed between us opening it and acquiring read lock '%s'. Attempting again.",
                    self.path,
                )
                os.close(fileno)
                continue
            break
        self.fileno = fileno
        logger.debug("PID file read lock acquired '%s'", self.path)
        return True

    def unlock(self) -> None:
        """Unlock the read lock."""
        assert self.fileno is not None, "Lock is already free."
        os.close(self.fileno)
        self.fileno = None

    @property
    def pid(self):
        autolock = False
        if self.fileno is None:
            if not self.lock():
                return -1
            autolock = True
        res = super().pid
        if autolock:
            self.unlock()
        return res

    @property
    def is_running(self) -> bool:
        """Check if there is running process with locked PID file."""
        do_lock = self.fileno is None
        if do_lock:
            if not self.lock():
                return False
        res = pid_is_running(self.pid)
        if do_lock:
            self.unlock()
        return res

    def __enter__(self):
        """Enter context with PID file locked for reading.

        Returns two results, self and boolean if lock was successful.
        """
        return self, self.lock()

    def __exit__(self, exc_type, exc_value, traceback):
        """Unlock when leaving context."""
        self.unlock()
