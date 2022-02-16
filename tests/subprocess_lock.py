"""The simple process that acquires the lock and holds it till it is notified to release it."""
import pathlib
import sys

from pidfilelock import PIDLock

from . import barrier


def main():
    tmp_path = pathlib.Path(sys.argv[1])
    lockpath = tmp_path / "lock"
    b_up = barrier.RBarrier(tmp_path / "barrier-lock-up")
    b_sub = barrier.WBarrier(tmp_path / "barrier-lock")

    lock = PIDLock(lockpath)
    lock.lock(block=True)
    b_sub.invoke()
    b_up.wait()
    lock.unlock(block=True)
    b_sub.invoke()


if __name__ == "__main__":
    main()
