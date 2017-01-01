import signal
import threading


class ShutdownHandler(object):
    """
    Sets the event for terminating threads / processes.
    """
    def __init__(self, exit_event):
        self.exit_event = exit_event

    def __call__(self, *args, **kwargs):
        self.exit_event.set()


def get_shutdown_objects(signals=None):
    signals = signals or []
    exit_event = threading.Event()
    handler = ShutdownHandler(exit_event)
    for _signal in signals:
        signal.signal(_signal, handler)
    return handler, exit_event


def get_thread_shutdown_objects():
    # threads listen on SIGINT and SIGHUP for termination
    return get_shutdown_objects(signals=(signal.SIGINT, signal.SIGHUP))


def get_worker_shutdown_objects():
    # workers are terminated on a SIGTERM signal
    return get_shutdown_objects(signals=(signal.SIGTERM,))
