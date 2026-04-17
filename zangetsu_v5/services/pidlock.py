"""PID file lock — ensures single-instance execution per service.

Usage in any service:
    from zangetsu_v5.services.pidlock import acquire_lock
    acquire_lock("arena_pipeline")  # blocks or exits if another instance running
"""
import os
import sys
import fcntl
import atexit
import signal

_PID_DIR = "/tmp/zangetsu_v5"
_lock_fd = None
_lock_path = None


def acquire_lock(service_name: str) -> None:
    """Acquire an exclusive file lock for the named service.

    If another instance holds the lock, prints a message and exits immediately.
    The lock is released on normal exit, SIGTERM, or SIGINT.
    """
    global _lock_fd, _lock_path

    os.makedirs(_PID_DIR, exist_ok=True)
    _lock_path = os.path.join(_PID_DIR, f"{service_name}.lock")

    try:
        # Open with "a" first to avoid truncating before we have the lock
        _lock_fd = open(_lock_path, "a+")
        fcntl.flock(_lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (IOError, OSError):
        # Another instance holds the lock — read existing PID safely
        existing_pid = "unknown"
        try:
            with open(_lock_path, "r") as f:
                existing_pid = f.read().strip() or "unknown"
        except Exception:
            pass
        print(
            f"[pidlock] {service_name}: another instance running (pid={existing_pid}). Exiting.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Lock acquired — now safe to write our PID
    _lock_fd.seek(0)
    _lock_fd.truncate(0)
    _lock_fd.write(str(os.getpid()))
    _lock_fd.flush()

    # Ensure cleanup on exit
    atexit.register(_release_lock)

    # Also handle SIGTERM gracefully
    _prev_term = signal.getsignal(signal.SIGTERM)
    _prev_int = signal.getsignal(signal.SIGINT)

    def _sig_handler(signum, frame):
        _release_lock()
        # Call previous handler if it was a callable
        prev = _prev_term if signum == signal.SIGTERM else _prev_int
        if callable(prev):
            prev(signum, frame)
        else:
            sys.exit(0)

    signal.signal(signal.SIGTERM, _sig_handler)
    signal.signal(signal.SIGINT, _sig_handler)


def _release_lock():
    global _lock_fd, _lock_path
    if _lock_fd is not None:
        try:
            fcntl.flock(_lock_fd.fileno(), fcntl.LOCK_UN)
            _lock_fd.close()
        except Exception:
            pass
        _lock_fd = None
    _lock_path = None
