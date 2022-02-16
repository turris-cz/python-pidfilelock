"""Common base for both PIDLock and PIDFile."""
import contextlib
import io
import os
import pathlib
import typing


class PIDBase(contextlib.AbstractContextManager):
    """The common base for both PIDLock and PIDFile implementing the common access routines to the PID file."""

    def __init__(self, path: typing.Union[str, pathlib.Path]):
        """Shared initializer for PID file lock handling classes.

        path: The path to the lock file
        """
        self.path = path if isinstance(path, pathlib.Path) else pathlib.Path(path)
        self.fileno: typing.Optional[int] = None  # Note: we use this to internally detect lock

    @property
    def pid(self) -> int:
        """Read the content of the PID file."""
        assert self.fileno is not None
        os.lseek(self.fileno, 0, os.SEEK_SET)
        return int(os.read(self.fileno, io.DEFAULT_BUFFER_SIZE))

    @property
    def is_locked(self) -> bool:
        """Check if file is locked by this instance."""
        return self.fileno is not None
