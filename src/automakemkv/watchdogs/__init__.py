"""
Utilities for ripping titles

"""

import signal
from threading import Event

RUNNING = Event()

signal.signal(signal.SIGINT, lambda *args: RUNNING.set())
signal.signal(signal.SIGTERM, lambda *args: RUNNING.set())
