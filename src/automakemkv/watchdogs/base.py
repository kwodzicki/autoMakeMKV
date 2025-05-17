"""
Utilities for ripping titles

"""

import logging

from PyQt5 import QtCore

from .. import ripper
from ..ui import dialogs

from . import RUNNING


class BaseWatchdog(QtCore.QThread):
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

    def __init__(self):
        super().__init__()
        self.log = logging.getLogger(__name__)
        self.log.debug("%s started", __name__)

        self.HANDLE_DISC.connect(self.handle_disc)

        self._outdir = None

        self.dbdir = None
        self.outdir = None
        self.everything = None
        self.extras = None
        self.convention = None
        self.root = None
        self.progress_dialog = None

        self._mounting = {}
        self._mounted = {}
        self._monitor = None

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
        self.convention = kwargs.get('convention', self.convention)

    def get_settings(self):

        return {
            'dbdir': self.dbdir,
            'outdir': self.outdir,
            'everything': self.everything,
            'extras': self.extras,
            'convention': self.convention,
        }

    def _ejecting(self, dev):

        proc = self._mounted.pop(dev, None)
        if proc is None:
            return

        if proc.isRunning():
            self.log.warning("%s - Killing the ripper process!", dev)
            proc.terminate(dev)
            return

    def quit(self, *args, **kwargs):
        RUNNING.set()

    def rip_failure(self, device: str):

        dialog = dialogs.RipFailure(device)
        dialog.exec_()

    def rip_success(self, device: str):

        dialog = dialogs.RipSuccess(device)
        dialog.exec_()

    @QtCore.pyqtSlot(str)
    def handle_disc(self, dev: str):

        obj = ripper.DiscHandler(
            dev,
            self.outdir,
            self.everything,
            self.extras,
            self.convention,
            self.dbdir,
            self.root,
            self.progress_dialog,
        )

        obj.FAILURE.connect(self.rip_failure)
        obj.SUCCESS.connect(self.rip_success)

        self._mounted[dev] = obj
