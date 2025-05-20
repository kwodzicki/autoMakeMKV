"""
Utilities for ripping titles

"""

import logging
from threading import Thread
from queue import Queue

from PyQt5 import QtWidgets, QtCore
import win32con
import win32file
import win32gui
import win32gui_struct

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

        # Use invisible QWidget to obtain an HWND
        self.hidden_window = QtWidgets.QWidget()
        self.hidden_window.setWindowFlags(QtCore.Qt.Widget | QtCore.Qt.Tool)
        self.hidden_window.hide()

        # Subclass native winEventProc
        self.hwnd = int(self.hidden_window.winId())
        self.old_proc = win32gui.SetWindowLong(
            self.hwnd,
            win32con.GWL_WNDPROC,
            self.event_handler,
        )

    def event_handler(self, hwnd, msg, wparam, lparam):
        if msg == win32con.WM_DEVICECHANGE and wparam is not None:
            try:
                dev_broadcast = win32gui_struct.UnpackDEV_BROADCAST(lparam)
            except Exception:
                pass
            else:
                if dev_broadcast and getattr(dev_broadcast, 'devicetype', None) == win32con.DBT_DEVTYP_VOLUME:
                    drives = self._mask_to_letters(dev_broadcast.unitmask)
                    for dev in drives:
                        if not self._is_cdrom(dev):
                            continue

                        if wparam != win32con.DBT_DEVICEARRIVAL:
                            self.log.debug("%s - Eject request", dev)
                            self._ejecting(dev)
                            continue

                        if dev in self._mounted:
                            self.log.info("%s - Device in mounted list", dev)
                            continue

                        self.log.debug("%s - Finished mounting", dev)
                        self._mounted[dev] = None
                        self.HANDLE_DISC.emit(dev)

        return win32gui.CallWindowProc(self.old_proc, hwnd, msg, wparam, lparam)

    def _mask_to_letters(self, mask):
        return [
            chr(65 + i) + ':'
            for i in range(26)
            if (mask >> i) & 1
        ]

    def _is_cdrom(self, drive_letter):
        try:
            return win32file.GetDriveType(f"{drive_letter}\\") == win32file.DRIVE_CDROM
        except:
            return False


    def start(self):
        """
        Overload as do not want the thread to start

        """

        pass



