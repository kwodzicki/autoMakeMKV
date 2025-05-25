"""
Utilities for ripping titles

"""

import logging

import win32con
import win32file
import win32gui
import win32gui_struct

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

    def __init__(self, *args, **kwargs):
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

        super().__init__(*args, **kwargs)
        self.log = logging.getLogger(__name__)

        # Subclass native winEventProc using the progress widget
        self.hwnd = int(self.progress.winId())
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
                device_type = getattr(dev_broadcast, 'devicetype', None)
                unitmask = getattr(dev_broadcast, 'unitmask', None)
                arrival = wparam == win32con.DBT_DEVICEARRIVAL
                self.process_device_change(device_type, unitmask, arrival)
        return win32gui.CallWindowProc(
            self.old_proc,
            hwnd,
            msg,
            wparam,
            lparam,
        )

    def process_device_change(self, device_type, unitmask, arrival: bool):
        if device_type != win32con.DBT_DEVTYP_VOLUME:
            return

        drives = self._mask_to_letters(unitmask)
        for dev in drives:
            if not self._is_cdrom(dev):
                continue

            if not arrival:
                self.log.debug("%s - Caught non-insert event", dev)
                continue

            self.log.debug("%s - Finished mounting", dev)
            self.HANDLE_INSERT.emit(dev)

    def _mask_to_letters(self, mask):
        return [
            chr(65 + i) + ':'
            for i in range(26)
            if (mask >> i) & 1
        ]

    def _is_cdrom(self, drive_letter):
        try:
            return (
                win32file.GetDriveType(f"{drive_letter}\\")
                == win32file.DRIVE_CDROM
            )
        except Exception:
            return False

    def start(self):
        """
        Overload as do not want the thread to start

        """

        pass
