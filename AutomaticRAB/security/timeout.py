import signal


def _timeout_handler(signum, frame):
    raise TimeoutError("Operation timed out")

def run_with_timeout(seconds, func, *args, **kwargs):
    """Run a function with a hard timeout."""
    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(seconds)
    try:
        return func(*args, **kwargs)
    finally:
        signal.alarm(0)
