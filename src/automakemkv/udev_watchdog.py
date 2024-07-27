"""
Utilities for ripping titles

"""

import logging
from collections.abc import Callable
import signal
from threading import Event

from PyQt5 import QtCore

import pyudev

from . import UUID_ROOT, OUTDIR, DBDIR
from . import paths
from . import ripper

KEY = 'DEVNAME'
CHANGE = 'DISK_MEDIA_CHANGE'
CDTYPE = "ID_CDROM"
STATUS = "ID_CDROM_MEDIA_STATE"
EJECT = "DISK_EJECT_REQUEST"  # This appears when initial eject requested
READY = "SYSTEMD_READY"  # This appears when disc tray is out

RUNNING = Event()

signal.signal(signal.SIGINT, lambda *args: RUNNING.set())
signal.signal(signal.SIGTERM, lambda *args: RUNNING.set())


class UdevWatchdog(QtCore.QThread):
    """
    Main watchdog for disc monitoring/ripping

    This thread will run a pyudev monitor instance, looking for changes in
    disc. On change, will spawn the DiscHandler object for handling loading
    of disc information from the database if exists, or prompting using for
    information via a GUI.

    After information is obtained, a rip of the requested/flagged tracks
    will start.

    """

    HANDLE_DISC = QtCore.pyqtSignal(str)

    def __init__(
        self,
        progress_dialog,
        outdir: str = OUTDIR,
        everything: bool = False,
        extras: bool = False,
        root: str = UUID_ROOT,
        filegen: Callable = paths.video_utils_outfile,
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
            filegen (func) : Function to use to generate
                output file names based on information
                from the database. This function must
                accept (outdir, info, extras=bool), where info is
                a dictionary of data loaded from the
                disc database, and extras specifies if
                extras should be ripped.

        """

        super().__init__()
        self.log = logging.getLogger(__name__)
        self.log.debug("%s started", __name__)

        self.HANDLE_DISC.connect(self.handle_disc)

        self._outdir = None

        self.dbdir = kwargs.get('dbdir', DBDIR)
        self.outdir = outdir
        self.everything = everything
        self.extras = extras
        self.root = root
        self.filegen = filegen
        self.progress_dialog = progress_dialog

        self._mounting = {}
        self._mounted = {}
        self._context = pyudev.Context()
        self._monitor = pyudev.Monitor.from_netlink(self._context)
        self._monitor.filter_by(subsystem='block')

    @property
    def outdir(self):
        return self._outdir

    @outdir.setter
    def outdir(self, val):
        self.log.info('Output directory set to : %s', val)
        self._outdir = val

    def set_settings(self, **kwargs):
        """
        Set options for ripping discs

        """

        self.log.debug('Updating ripping options')
        self.dbdir = kwargs.get('dbdir', self.dbdir)
        self.outdir = kwargs.get('outdir', self.outdir)
        self.everything = kwargs.get('everything', self.everything)
        self.extras = kwargs.get('extras', self.extras)

    def get_settings(self):

        return {
            'dbdir': self.dbdir,
            'outdir': self.outdir,
            'everything': self.everything,
            'extras': self.extras,
        }

    def run(self):
        """
        Processing for thread

        Polls udev for device changes, running MakeMKV pipelines
        when dvd/bluray found

        """

        self.log.info('Watchdog thread started')
        while not RUNNING.is_set():
            device = self._monitor.poll(timeout=1.0)
            if device is None:
                continue

            # Get value for KEY. If is None, then did not exist, so continue
            dev = device.properties.get(KEY, None)
            if dev is None:
                continue

            # Every optical drive should support CD, so check if the device
            # has the CDTYPE flag, if not we ignore it
            if device.properties.get(CDTYPE, '') != '1':
                continue

            if device.properties.get(EJECT, ''):
                self.log.debug("%s - Eject request", dev)
                self._ejecting(dev)
                continue

            if device.properties.get(READY, '') == '0':
                self.log.debug("%s - Drive is ejectecd", dev)
                self._ejecting(dev)
                continue

            if device.properties.get(CHANGE, '') != '1':
                self.log.debug(
                    "%s - Not a '%s' event, ignoring",
                    dev,
                    CHANGE,
                )
                continue

            if device.properties.get(STATUS, '') != 'complete':
                self.log.debug(
                    "%s - Caught event that was NOT insert/eject, ignoring",
                    dev,
                )
                continue

            if dev in self._mounted:
                self.log.info("%s - Device in mounted list", dev)
                continue

            self.log.debug("%s - Finished mounting", dev)
            self._mounted[dev] = None
            self.HANDLE_DISC.emit(dev)

    def _ejecting(self, dev):

        proc = self._mounted.pop(dev, None)
        if proc is None:
            return

        if proc.isRunning():
            self.log.warning("%s - Killing the ripper process!", dev)
            proc.terminate()
            return

    def quit(self, *args, **kwargs):
        RUNNING.set()

    @QtCore.pyqtSlot(str)
    def handle_disc(self, dev: str):

        self._mounted[dev] = ripper.DiscHandler(
            dev,
            self.outdir,
            self.everything,
            self.extras,
            self.dbdir,
            self.root,
            self.filegen,
            self.progress_dialog,
        )
