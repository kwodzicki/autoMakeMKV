"""
Utilities for ripping titles

"""

import signal
from threading import Event

RUNNING = Event()


def set_event(*args, **kwargs):
    print('Caught signal')
    RUNNING.set()


signal.signal(signal.SIGINT, set_event)
signal.signal(signal.SIGTERM, set_event)
