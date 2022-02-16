"""Various utilities that can be used by users of this library.
"""
import contextlib
import grp
import os
import pathlib
import pwd
import stat
import typing

from .file import PIDFile
from .lock import DEFAULT_LOCK_MODE, PIDLock


def mklockdir(
    path: typing.Union[str, pathlib.Path],
    mode: int = stat.S_IRWXU | stat.S_IRWXG | stat.S_IROTH | stat.S_IXOTH,
    user: typing.Union[str, int] = -1,
    group: typing.Union[str, int] = -1,
    parents: bool = False,
    exist_ok: bool = True,
) -> None:
    """Create directory suitable for PID file locks to be created in.

    path: The path to directory to be created
    mode: The mode for the new directory
    user: The owner the directory should have
    group: The group the directory should be assigned to
    parents: If parent directories should be created
    exist_ok: If it is ok if directory already exists
    """
    path = path if isinstance(path, pathlib.Path) else pathlib.Path(path)
    path.mkdir(mode=mode, parents=parents, exist_ok=exist_ok)
    uid = user if isinstance(user, int) else pwd.getpwnam(user).pw_uid
    gid = group if isinstance(group, int) else grp.getgrnam(group).gr_gid
    pthstat = path.stat()
    if uid in (-1, pthstat.st_uid) or gid in (-1, pthstat.st_gid):
        # Note: we can't change ownership if we are not owner. This results in exception. We intentionally cause it here
        # to report it as an error if uid or gid not matches.
        os.chown(path, uid, gid)


@contextlib.contextmanager
def opportunistic_lock(
    path: typing.Union[str, pathlib.Path],
    mode: int = DEFAULT_LOCK_MODE,
    group: typing.Optional[typing.Union[str, int]] = None,
    unsafe_cleanup: bool = False,
    unlock_block: bool = False,
) -> typing.Generator[typing.Union[PIDLock, PIDFile], None, None]:
    """Either lock the PID file (returning PIDLock) or acquire the read lock (returning PIDFile).

    The use case for this is when you are implementing service that does not run all the time but you still want to have
    only one instance at one time performing the job. The service is simply started if the lock is acquired or it
    connects to the running service if there is already one running.
    """
    pidlock = PIDLock(path, mode, group, unsafe_cleanup)
    pidfile = PIDFile(path)
    # We have to attempt in the cycle because we do not have any mechanism to try to lock for both. Thus we try one
    # after the other and see which one is the successful.
    while True:
        if pidlock.lock(block=False):
            try:
                yield pidlock
            finally:
                pidlock.unlock(unlock_block)
            return
        with pidfile as _:
            if pidfile.is_running:
                yield pidfile
                return
