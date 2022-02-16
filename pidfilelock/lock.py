"""The pidfilelock implementation."""
import fcntl
import grp
import io
import logging
import os
import pathlib
import stat
import typing

from ._base import PIDBase as _PIDBase
from .tools import pid_is_running

logger = logging.getLogger(__name__)

DEFAULT_LOCK_MODE = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH


class PIDLock(_PIDBase):
    """The primary pidfilelock class implementing the lock mechanism.

    You should use this in the process you want to take lock in.

    TLDR; Always make sure that anyone who is going to lock the PID file has write access to the file as well as to the
    directory that file is stored in. The directory can't have sticky bit set.
    To take the lock you have to make sure that caller has write permission to both the lock file as well as directory
    it resides in. The need for write permission on directory should be clear, without it it is not possible to create
    the lock file. The need for lock file to be writable might not be clear as owner of the lock removes it in the end.
    Problem is that it might not be true every time and we have to be able to safely clean it. That consist of locking
    and removing it. To make this work the directory can't have sticky bit set as otherwise we can't remove it.
    """

    def __init__(
        self,
        path: typing.Union[str, pathlib.Path],
        mode: int = DEFAULT_LOCK_MODE,
        group: typing.Optional[typing.Union[str, int]] = None,
        unsafe_cleanup: bool = False,
    ):
        """Set attributes and prepare for locking.

        Initialization does not yet takes the lock. It only verifies parameters and sets them as attributes.

        path: The path to the lock file
        mode: The mode applied to the lock file. Set this appropriately so anyone that could take lock has write access
          and anyone querying lock has at least read access.
        group: The lock is created in default as owned by the user's current primary group but this allows you to select
          the different group. This is handy if you want to allow locking to anyone from specific group.
        unsafe_cleanup: Allows unsafe recovery in case we have write access to the directory but not to the file. It is
          unsafe because it won't check if process is still running without possible and probable race condition.
        """
        super().__init__(path)
        self.mode = mode
        self.group = grp.getgrnam(group).gr_gid if isinstance(group, str) else group
        self.unsafe_cleanup = unsafe_cleanup

    def __del__(self):
        if self.fileno is not None:
            self.unlock()

    def lock(self, block: bool = True) -> bool:
        """Lock the PID file and store our PID to it.

        block: block execution until we acquire the lock.

        Returns True if lock was succesfull or False otherwise. It never returns False if block is set to True.
        """
        assert self.fileno is None, "Lock is already obtained."
        while True:
            try:
                fileno = os.open(self.path, os.O_RDWR | os.O_CREAT, mode=self.mode)
            except PermissionError:
                if not self.unsafe_cleanup:
                    raise
                self._unsafe_cleanup()
                continue
            try:
                fcntl.flock(fileno, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                if not block:
                    os.close(fileno)
                    return False
                logger.info("Waiting for PID file lock '%s'.", self.path)
                fcntl.flock(fileno, fcntl.LOCK_EX)
            logger.debug("PID file exclusively locked '%s'", self.path)
            # We have exclusive lock but we have to verify that it is for file that is really on FS and that it is ours
            if not self._lock_verify(fileno):
                os.close(fileno)
                continue
            break
        # We have exclusive lock and file is owned by us from now on
        if self.group is not None:  # Explicitly set the configured group
            os.fchown(fileno, -1, self.group)
        os.lseek(fileno, 0, os.SEEK_SET)
        os.truncate(fileno, 0)  # We might be overtaking it after ourself with some content so truncate.
        os.write(fileno, str(os.getpid()).encode())
        fcntl.flock(fileno, fcntl.LOCK_SH)  # downgrade the lock to allow others to read the content
        self.fileno = fileno
        logger.debug("PID file lock acquired '%s'", self.path)
        return True

    def _unsafe_cleanup(self):
        # TODO this is missing and needs to be implemented.
        raise NotImplementedError

    def _lock_verify(self, fileno):
        fstat = os.fstat(fileno)
        if self.path.stat().st_ino != fstat.st_ino:
            logger.debug(
                "The PID lock file was removed between us opening it and acquiring lock '%s', attempting again.",
                self.path,
            )
            return False
        content = os.read(fileno, io.DEFAULT_BUFFER_SIZE).decode()
        if content and pid_is_running(int(content)):
            # We downgrade from exclusive lock to shared one later on. That is implemented in kernel as unlock and
            # only then new lock. After unlock the lock can be assigned to any process waiting for lock. Thus we
            # have to check if the original author is not running and release it if it does.
            logger.debug(
                "The PID the file '%s' contains belongs to the running process %s. Attempting again.",
                self.path,
                content,
            )
            return False
        if fstat.st_uid != os.getuid():
            logger.debug(
                "The PID lock file is not owned by us '%s' but by UID %d. Removing the file and attempting again.",
                self.path,
                fstat.st_uid,
            )
            self.path.unlink()
            return False
        return True

    def unlock(self, block: bool = False) -> None:
        """Remove the PID file.

        block: block until all read locks are freed (PIDFile). This is handy if you use PID file to communicate between
          instances as blocking here prevents issues where PIDFile process tries to communicate with terminated PIDLock
          process.
        """
        assert self.fileno is not None, "Lock is already free."
        if block:
            try:
                fcntl.flock(self.fileno, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                logger.info("Waiting for all locks to be unlocked '%s'.", self.path)
                fcntl.flock(self.fileno, fcntl.LOCK_EX)
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass  # We want to remove it so if somehow it is removed we just ignore the error
        os.close(self.fileno)  # We close only after unlink to make sure that we still hold the lock in the meantime
        self.fileno = None

    def __enter__(self):
        """Enter context with locked file.

        This is blocking call.
        """
        self.lock()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Unlock when leaving context."""
        self.unlock()
