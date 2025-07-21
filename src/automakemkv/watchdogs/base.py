"""
Utilities for ripping titles

"""

import logging
import sys
from subprocess import Popen

from PyQt5 import QtCore

if sys.platform.startswith('win'):
    import ctypes

from .. import UUID_ROOT, OUTDIR, DBDIR
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

    HANDLE_INSERT = QtCore.pyqtSignal(str)
    HANDLE_EJECT = QtCore.pyqtSignal(str)
    EJECT_DISC = QtCore.pyqtSignal()

    def __init__(
        self,
        progress,
        *args,
        outdir: str = OUTDIR,
        everything: bool = False,
        extras: bool = False,
        convention: str = 'video_utils',
        root: str = UUID_ROOT,
        cleanup: bool = True,
        **kwargs,
    ):
        super().__init__()
        self.log = logging.getLogger(__name__)

        self.HANDLE_INSERT.connect(self.handle_insert)

        self._cleanup = cleanup
        self._outdir = None
        self._tmpdir = None
        self._mounted = []
        self._failure = []
        self._success = []

        self.progress = progress

        self.dbdir = kwargs.get('dbdir', DBDIR)
        self.tmpdir = kwargs.get('tmpdir', outdir)
        self.outdir = outdir
        self.everything = everything
        self.extras = extras
        self.convention = convention
        self.root = root

    @property
    def outdir(self):
        return self._outdir

    @outdir.setter
    def outdir(self, val):
        self.log.info('Output directory set to : %s', val)
        self._outdir = val

    @property
    def tmpdir(self):
        return self._tmpdir

    @tmpdir.setter
    def tmpdir(self, val):
        self.log.info('Temporary directory set to : %s', val)
        self._tmpdir = val

    def set_settings(self, **kwargs):
        """
        Set options for ripping discs

        """

        self.log.debug('Updating ripping options')
        self.dbdir = kwargs.get('dbdir', self.dbdir)
        self.outdir = kwargs.get('outdir', self.outdir)
        self.tmpdir = kwargs.get('tmpdir', self.tmpdir)
        self.everything = kwargs.get('everything', self.everything)
        self.extras = kwargs.get('extras', self.extras)
        self.convention = kwargs.get('convention', self.convention)

    def get_settings(self):

        return {
            'dbdir': self.dbdir,
            'outdir': self.outdir,
            'tmpdir': self.tmpdir,
            'everything': self.everything,
            'extras': self.extras,
            'convention': self.convention,
        }

    def quit(self, *args, **kwargs):
        RUNNING.set()

    @QtCore.pyqtSlot(str)
    def rip_failure(self, fname: str):

        dev = self.sender().dev
        dialog = dialogs.RipFailure(dev, fname)
        self._failure.append(dialog)
        dialog.FINISHED.connect(self._failure_closed)
        dialog.exec_()

    @QtCore.pyqtSlot(int)
    def _failure_closed(self, res: int):
        obj = self.sender()
        if obj in self._failure:
            self._failure.remove(obj)
        obj.deleteLater()

    @QtCore.pyqtSlot(str)
    def rip_success(self, fname: str):
        """
        Display dialog to signal failed rip

        """

        dev = self.sender().dev
        dialog = dialogs.RipSuccess(dev, fname)
        self._success.append(dialog)
        dialog.FINISHED.connect(self._success_closed)
        dialog.exec_()

    @QtCore.pyqtSlot(int)
    def _success_closed(self, res: int):
        obj = self.sender()
        if obj in self._success:
            self._success.remove(obj)
        obj.deleteLater()

    @QtCore.pyqtSlot()
    def rip_finished(self):
        """
        Display timed dialog to signal successful rip

        """

        sender = self.sender()
        self.log.debug("%s - Processing finished event", sender.dev)
        sender.cancel(sender.dev)
        if sender in self._mounted:
            self._mounted.remove(sender)
        else:
            self.log.warning(
                "%s - Did not find sender object in _mounted",
                sender.dev,
            )

        sender.deleteLater()

    @QtCore.pyqtSlot(str)
    def handle_insert(self, dev):

        obj = ripper.DiscHandler(
            dev,
            self.outdir,
            self.tmpdir,
            self.everything,
            self.extras,
            self.convention,
            self.dbdir,
            self.root,
            self.progress,
            cleanup=self._cleanup,
        )

        obj.FAILURE.connect(self.rip_failure)
        obj.SUCCESS.connect(self.rip_success)
        obj.FINISHED.connect(self.rip_finished)
        obj.EJECT_DISC.connect(self.eject_disc)
        self._mounted.append(obj)

    @QtCore.pyqtSlot()
    def eject_disc(self) -> None:
        """
        Eject the disc

        """

        dev = self.sender().dev
        self.log.debug("%s - Ejecting disc", dev)

        if sys.platform.startswith('linux'):
            _ = Popen(['eject', dev])
        elif sys.platform.startswith('win'):
            command = f"open {dev}: type CDAudio alias drive"
            ctypes.windll.winmm.mciSendStringW(command, None, 0, None)
            ctypes.windll.winmm.mciSendStringW(
                "set drive door open",
                None,
                0,
                None,
            )
            ctypes.windll.winmm.mciSendStringW("close drive", None, 0, None)
