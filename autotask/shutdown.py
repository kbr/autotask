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


def get_shutdown_objects():
    """
    Returns a tuple of n instance from ShutdownHandler and a
    corresponding threading-Event.
    The returned handler is registered for most common terminate signals
    (without SIGKILL because intercepting a kill 9 command is not
    possible).
    """
    signals = (signal.SIGHUP, signal.SIGINT,
               signal.SIGQUIT, signal.SIGTERM, signal.SIGXCPU)
    exit_event = threading.Event()
    handler = ShutdownHandler(exit_event)
    for _signal in signals:
        signal.signal(_signal, handler)
    return handler, exit_event
