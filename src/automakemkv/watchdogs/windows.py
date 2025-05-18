"""
Utilities for ripping titles

"""

import logging
from threading import Thread
from queue import Queue

import wmi
import pythoncom

from .. import UUID_ROOT, OUTDIR, DBDIR

from . import RUNNING
from .base import BaseWatchdog


class Watchdog(BaseWatchdog):
    """
    Main watchdog for disc monitoring/ripping

    This thread will run a pyudev monitor instance, looking for changes in
    disc. On change, will spawn the DiscHandler object for handling loading
    of disc information from the database if exists, or prompting using for
    information via a GUI.

    After information is obtained, a rip of the requested/flagged tracks
    will start.

    """

    def __init__(
        self,
        progress_dialog,
        outdir: str = OUTDIR,
        everything: bool = False,
        extras: bool = False,
        convention: str = 'video_utils',
        root: str = UUID_ROOT,
        **kwargs,
    ):
        """
        Arguments:
            outdir (str) : Top-level directory for ripping files

        Keyword arguments:
            everything (bool) : If set, then all titles identified
                for ripping will be ripped. By default, only the
                main feature will be ripped
            extras (bool) : If set, only 'extra' features will
                be ripped along with the main title(s). Main
                title(s) include Theatrical/Extended/etc.
                versions for movies, and episodes for series.
            root (str) : Location of the 'by-uuid' directory
                where discs are mounted. This is used to
                get the unique ID of the disc.

        """

        super().__init__()
        self.log = logging.getLogger(__name__)

        self.dbdir = kwargs.get('dbdir', DBDIR)
        self.outdir = outdir
        self.everything = everything
        self.extras = extras
        self.convention = convention
        self.root = root
        self.progress_dialog = progress_dialog

        self._monitor = OpticalMediaDetector()
        self._monitor.start()

    def run(self):
        """
        Processing for thread

        Polls udev for device changes, running MakeMKV pipelines
        when dvd/bluray found

        """

        self.log.info('Watchdog thread started')
        while not RUNNING.is_set():
            try:
                info = self._monitor.poll(timeout=1.0)
            except Exception:
                continue
            
            if info is None:
                continue

            action, dev = info
            if action == 'unmount':
                self.log.debug("%s - Eject request", dev)
                self._ejecting(dev)
                continue

            if dev in self._mounted:
                self.log.info("%s - Device in mounted list", dev)
                continue

            self.log.debug("%s - Finished mounting", dev)
            self._mounted[dev] = None
            self.HANDLE_DISC.emit(dev)


class OpticalMediaDetector(Thread):
    def __init__(self, interval: int | float = 5.0):
        super().__init__()
        self.log = logging.getLogger(__name__)
        self.interval = max(interval, 2.0)  # Ensure at least 2 seconds
        self.queue = Queue()

    def run(self):
        pythoncom.CoInitialize()
        wmi_obj = wmi.WMI()
        previous_status = get_cdrom_status(wmi_obj)
        while not RUNNING.wait(timeout=self.interval):
            current_status = get_cdrom_status(wmi_obj)
    
            for drive in current_status:
                was_loaded = previous_status.get(drive, False)
                is_loaded = current_status[drive]

                action = None
                if not was_loaded and is_loaded:
                    action = 'mount'
                    self.log.debug("Media inserted into drive '%s'", drive)
                elif was_loaded and not is_loaded:
                    action = 'unmount'
                    self.log.debug("Media ejected from drive '%s'", drive)

                if action is not None:
                    self.queue.put((action, drive))

            previous_status = current_status
        self.queue.put(None)

    def poll(self, *args, **kwargs):

        # Try to get item from queue.
        # On fail, reraise exception
        # On pass, signal task done
        try:
            res = self.queue.get(*args, **kwargs)
        except Exception as err:
            raise err
        else:
            self.queue.task_done()

        return res


def get_cdrom_status(c):
    """Returns a dict of {drive_letter: has_media (bool)}"""
    status = {}
    for cdrom in c.Win32_CDROMDrive():
        drive = cdrom.Drive
        try:
            has_media = cdrom.MediaLoaded
        except:
            has_media = False
        status[drive] = has_media
    return status