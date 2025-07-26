"""
Utilities for ripping titles

"""

import logging
import sys
from subprocess import Popen

from PyQt5 import QtCore

if sys.platform.startswith('win'):
    import ctypes

from .. import UUID_ROOT
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
        root: str = UUID_ROOT,
        cleanup: bool = True,
        **kwargs,
    ):
        super().__init__()
        self.log = logging.getLogger(__name__)

        self.HANDLE_INSERT.connect(self.handle_insert)

        self._cleanup = cleanup
        self._mounted = []
        self._failure = []
        self._success = []

        self.progress = progress
        self.root = root

    def quit(self, *args, **kwargs):
        RUNNING.set()

    @QtCore.pyqtSlot(str)
    def rip_failure(self, fname: str):

        sender = self.sender()
        sender.join()  # Wait for thread to finish
        dev = sender.dev
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

        sender = self.sender()
        sender.join()  # Wait for thread to finish
        dev = sender.dev
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
        sender.join()  # Wait for thread to finish
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
    def handle_insert(self, dev: str):

        obj = ripper.DiscHandler(
            dev,
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
