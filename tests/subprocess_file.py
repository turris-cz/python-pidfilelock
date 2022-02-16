"""The simple process that acquires the read lock and holds it till it is notified to release it."""
import pathlib
import sys

from pidfilelock import PIDFile

from . import barrier


def main():
    tmp_path = pathlib.Path(sys.argv[1])
    lockpath = tmp_path / "lock"
    b_up = barrier.RBarrier(tmp_path / "barrier-file-up")
    b_sub = barrier.WBarrier(tmp_path / "barrier-file")

    file = PIDFile(lockpath)
    b_up.wait()
    assert file.lock()
    b_sub.invoke()
    b_up.wait()
    file.unlock()


if __name__ == "__main__":
    main()
