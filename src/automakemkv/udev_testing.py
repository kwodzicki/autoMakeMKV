"""
Utilities for ripping titles

"""

import logging
from threading import Event, Thread

import pyudev

KEY = 'DEVNAME'
CHANGE = 'DISK_MEDIA_CHANGE'
CDTYPE = "ID_CDROM"
STATUS = "ID_CDROM_MEDIA_STATE"
EJECT = "DISK_EJECT_REQUEST"  # This appears when initial eject requested
READY = "SYSTEMD_READY"  # This appears when disc tray is out

RUNNING = Event()


class UdevWatchdog(Thread):
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

        self._mounted = {}
        self._context = pyudev.Context()
        self._monitor = pyudev.Monitor.from_netlink(self._context)
        self._monitor.filter_by(subsystem='block')

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
                continue

            if device.properties.get(READY, '') == '0':
                self.log.debug("%s - Drive is ejectecd", dev)
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


if __name__ == "__main__":

    log = logging.getLogger()
    log.setLevel(0)
    log.addHandler(logging.StreamHandler())

    inst = UdevWatchdog()
    inst.start()
