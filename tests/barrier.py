"""We need to perform tests on multiple processes and thus we need multiprocess barriers but based on named pipes."""
import abc
import os
import pathlib


class _Barrier(abc.ABC):
    """The base implementation of barrier."""

    def __init__(self, path: pathlib.Path, read: bool):
        """Make sure that barrier exists.

        path: path to the barrier fifo
        """
        self.path = path
        try:
            os.mkfifo(path)
        except FileExistsError:
            pass
        self.fileno = os.open(path, os.O_RDONLY if read else os.O_WRONLY)
        self.count = 0

    def close(self):
        """Close the barrier fifo file."""
        os.close(self.fileno)


class WBarrier(_Barrier):
    """Write barrier implementing invoke."""

    def __init__(self, path: pathlib.Path):
        """Open write side of the barrier.

        path: the path to the barrier fifo
        """
        super().__init__(path, False)

    def invoke(self, count: int = 1):
        """Invoke barrier the given number of times."""
        while count > 0:
            os.write(self.fileno, self.count.to_bytes(1, "big"))
            count -= 1
            self.count += 1


class RBarrier(_Barrier):
    """Read barrier implementing waiting."""

    def __init__(self, path: pathlib.Path):
        """Open read side of the barrier.

        path: the path to the barrier fifo
        """
        super().__init__(path, True)

    def wait(self, count: int = 1):
        """Wait for given number of barrier wakes."""
        while count > 0:
            os.read(self.fileno, 1)
            count -= 1
            self.count += 1
