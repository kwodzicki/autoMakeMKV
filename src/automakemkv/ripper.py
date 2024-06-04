"""
Utilities for ripping titles

"""

import logging
from logging.handlers import QueueHandler
import argparse
import os
import signal
import time
import subprocess
import multiprocessing as mp
from threading import Thread, Event
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot

import pyudev

from . import UUID_ROOT, DBDIR, LOG, STREAM
from .mediaInfo.gui import DiscDialog, ExistingDiscOptions, RIP, SAVE, OPEN, IGNORE
from .mediaInfo.utils import getDiscID, loadData
from .makemkv import MakeMKVRip
from .utils import video_utils_outfile, logger_thread, get_vendor_model

KEY = 'DEVNAME'
CHANGE = 'DISK_MEDIA_CHANGE'
STATUS = "ID_CDROM_MEDIA_STATE"
SIZE_POLL = 10

RUNNING = Event()

signal.signal(signal.SIGINT, lambda *args : RUNNING.set())
signal.signal(signal.SIGTERM, lambda *args : RUNNING.set())


class RipperWatchdog(QThread):
    """
    Main watchdog for disc monitoring/ripping

    This function will run a pyudev monitor instance,
    looking for changes in disc. On change, will
    spawn the getTitleInfo() function, loading
    information from the database if exists, or
    prompting using for information via a GUI.

    After information is obtained, a rip of the
    requested/flagged tracks will start.

    The logic for disc mounting is a bit obtuse, so will try to explain.
    When the disc is initially inserted, it should trigger an event where
    the CHANGE property is set. As the dev should NOT be in mounted list,
    we add it to the mounting list. The next event for that dev is the event
    that the disc is fully mounted. This will NOT have the CHANGE property.
    As the disc is still in the mounting list at this point, will NOT enter
    the if-statement there and will remove dev from mounting list, add dev
    to mounted list, and then run the ripping process.

    On future calls without the CHANGE property, the dev will NOT be in
    the mounting list, so we will just skip them. For an event WITH the
    CHANGE property, since the dev IS in the mounted list, we remove it
    from the mounted list and log information that it has been ejected.

    """

    MOUNT_SIGNAL = pyqtSignal(str)

    def __init__(
        self,
        outdir,
        everything=False,
        extras=False,
        root=UUID_ROOT,
        fileGen=video_utils_outfile,
        progress_dialog=None,
        **kwargs,
    ):
        """
        Arguments:
            outdir (str) : Top-level directory for ripping
                files
    
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
            fileGen (func) : Function to use to generate
                output file names based on information
                from the database. This function must
                accept (outdir, info, extras=bool), where info is
                a dictionary of data loaded from the
                disc database, and extras specifies if
                extras should be ripped.

        """

        super().__init__() 
        self.__log = logging.getLogger(__name__)
        self.__log.debug("%s started", __name__)

        self.MOUNT_SIGNAL.connect(self.get_disc_info)
 
        self._outdir = None
 
        self.dbdir = kwargs.get('dbdir', DBDIR)
        self.outdir = outdir
        self.everything = everything
        self.extras = extras
        self.root = root
        self.fileGen = fileGen
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
        #os.makedirs(val, exist_ok=True)
        self.__log.info('Output directory set to : %s', val)
        self._outdir = val

    def set_settings(self, **kwargs):
        """
        Set options for ripping discs

        """

        self.__log.debug('Updating ripping options')
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

        Polls udev for device changes, running MakeMKV pipelines when dvd/bluray
        found

        """

        self.__log.info('Watchdog thread started')
        while not RUNNING.is_set():
            device = self._monitor.poll(timeout=1.0)
            if device is None:
                continue

            # Get value for KEY. If is None, then did not exist, so continue
            dev = device.properties.get(KEY, None)
            if dev is None:
                continue

            # If we did NOT change an insert/eject event
            if device.properties.get(CHANGE, None):
                if device.properties.get(STATUS, '') != 'complete':
                    self.__log.debug(
                        'Caught event that was NOT insert/eject, ignoring : %s',
                        dev,
                    )
                    continue
                self.__log.debug('Finished mounting : %s', dev)
                self.MOUNT_SIGNAL.emit(dev)
                self._mounted[dev] = None 
                continue

            # If dev is NOT in mounted, initialize to False
            if dev not in self._mounted:
                self.__log.info('Odd event : %s', dev)
                continue

            self.__log.info('Device has been ejected : %s', dev)
            proc = self._mounted.pop(dev)
            if proc.is_alive():
                self.__log.warning('Killing the ripper process!')
                proc.kill()
                continue

            self.__log.debug(
                "Exitcode from ripping processes : %d",
                proc.exitcode,
            )

    def quit(self, *args, **kwargs):
        RUNNING.set()

    @pyqtSlot(str)
    def get_disc_info(self, dev):
        """
        Get information about a disc 
    
        Given the /dev path to a disc, load information from database if it exists or
        open GUI for user to input information
    
        Arguments:
            dev (str) : Device to rip from
    
        """
    
        # Attept to get UUID of disc
        uuid = getDiscID(dev, self.root)
        if uuid is None:
            self.__log.info("No UUID found for disc: %s", dev)
            return

        # Get title informaiton for tracks to rip
        self.__log.info("UUID of disc: %s", uuid)
        info, sizes = loadData(discID=uuid)
        if info is None:
            # Open dics metadata GUI and register "callback" for when closes
            self.disc_dialog(dev)
            return

        # Update mounted information and run rip_disc
        self._mounted[dev] = (info, sizes)
        self.options_dialog = ExistingDiscOptions()
        self.options_dialog.finished.connect(self.handle_disc_info)
 
    @pyqtSlot(int)
    def handle_disc_info(self, result):
        """
        Rip a whole disc
    
        Given information about a disc, rip
        all tracks. Intended to be run as thread
        so watchdog can keep looking for new discs
    
        Arguments:
            dev (str) : Device to rip from
            root (str) : Location of the 'by-uuid' directory
                where discs are mounted. This is used to
                get the unique ID of the disc.
            outdir (str) : Directory to save mkv files to
            extras (bool) : Flag for if should rip extras
    
        """

        # Get list of keys for mounted devices, then iterate over them
        devs = list(self._mounted.keys())
        for dev in devs:
            # Try to pop of information
            disc_info = self._mounted.pop(dev, None)
            if disc_info is None:
                continue

            # Check the "return" status of the dialog
            if result == IGNORE:
                self.__log.info('Ignoring disc: %s', dev)
                return

            # Get information about disc
            if isinstance(disc_info, tuple):
                info, sizes = disc_info
            else:
                info, sizes = disc_info.info, disc_info.sizes

            # Initialize ripper object
            if result == RIP:
                self.rip_disc(dev, info, sizes)
                return

            if result == SAVE:
                self.__log.info("Requested metadata save and eject: %s", dev)
                subprocess.call(['eject', dev])
                return

            if result == OPEN:
                self.disc_dialog(dev, discid=getDiscID(dev, self.root))
                return

            self.__log.error("Unrecognized option: %d", result)

    def disc_dialog(self, dev, discid=None):

        # Open dics metadata GUI and register "callback" for when closes
        dialog = DiscDialog(
            dev,
            dbdir=self.dbdir,
            discid=discid,
        )
        dialog.finished.connect(self.handle_disc_info)
        self._mounted[dev] = dialog

    def rip_disc(self, dev, info, sizes):

        # Initialize ripper object
        ripper = Ripper(
            dev,
            info,
            sizes,
            self.fileGen,
            self.get_settings(),
            progress=self.progress_dialog,
        )
        ripper.start()
        self._mounted[dev] = ripper


class Ripper(QThread):

    def __init__(self, dev, info, sizes, fileGen, settings, progress=None):
        super().__init__()
        self.log  = logging.getLogger(__name__)
        self.dev = dev
        self.info = info
        self.sizes = sizes
        self.fileGen = fileGen
        self.settings = settings
        self.progress = progress

        self.logthread = None

    def rip_disc(self):

        if self.info is None:
            self.log.error("No title information found/entered : %s", self.dev)
            return
 
        if self.info == 'skiprip':
            self.log.info("Just saving metadata, not ripping : %s", self.dev)
            return

        filegen = self.fileGen(
            self.settings['outdir'],
            self.info,
            everything=self.settings['everything'],
            extras=self.settings['extras'],
        )

        info = {
            title: {
                'path': fpath,
                'size': self.sizes[title],
            }
            for title, fpath in filegen
        }

        if self.progress is not None:
            self.log.info('Emitting add disc signal')
            self.progress.ADD_DISC.emit(self.dev, info)

        for title, info in info.items():
            self.rip_title(title, info['path'])

    def rip_title(self, title, outfile):
        """
        Rip a given title from a disc
    
        Rip a title from the given disc to 
        a specific output file.
    
        Arguments:
            title (str) : Title to rip
            outfile (str) : Name of the output file
    
        Returns:
            bool : True if ripped, False otherwise
    
        """
    
        outdir = os.path.dirname( outfile )
        if not os.path.isdir( outdir ):
            os.makedirs( outdir )
    
        tmpdir = os.path.splitext(
            os.path.basename(outfile),
        )[0]
        tmpdir = os.path.join(outdir, tmpdir)
        self.log.debug("Creating temporary directory : '%s'", tmpdir)
        os.makedirs(tmpdir, exist_ok=True)
    
        if self.progress is not None:
            self.progress.CUR_TRACK.emit(self.dev, title)
    
        self.log.info("[%s - %s] Ripping track", self.dev, title)
        self.mkv_thread = MakeMKVRip(
            self.dev,
            title,
            tmpdir,
            noscan=True,
            minlength=0,
        )
        self.mkv_thread.start()

        while not RUNNING.wait(timeout=SIZE_POLL) and self.mkv_thread.isRunning():
            if self.progress is None:
                continue
            self.progress.TRACK_SIZE.emit(self.dev, directory_size(tmpdir))
    
        if RUNNING.is_set():
            self.mkv_thread.quit()
            self.mkv_thread.wait()
            return
    
        files = [
            os.path.join(tmpdir, item) for item in os.listdir(tmpdir)
        ]
    
        status = False
        if self.mkv_thread.returncode != 0:
            for fname in files:
                os.remove(fname)
            self.log.error("Error ripping track '%s' from '%s'", title, self.dev)
        elif len(files) != 1:
            self.log.error('Too many output files!')
            for fname in files:
                os.remove( fname )
        else:
            self.log.info("Renaming file '%s' ---> '%s'", files[0], outfile)
            os.rename( files[0], outfile )
            status = True
    
        os.rmdir( tmpdir )
    
        return status

    def run(self):
        self.rip_disc()
        subprocess.call(['eject', self.dev]) 

    def kill(self):
        if self.mkv_thread is None:
            return
        self.mkv_thread.quit()

def directory_size(path):
    """
    Get size of all files in directory

    """

    return sum(
        d.stat().st_size
        for d in os.scandir(path)
        if d.is_file()
    )


def cli():
    parser = argparse.ArgumentParser()
    parser.add_argument( 'outdir',     type=str, help='Directory to save ripped titles to')
    parser.add_argument( '--loglevel', type=int, default=30, help='Set logging level')
    parser.add_argument( '--all',    action='store_true', help="If set, all tiltes (main and extra) will be ripped" )
    parser.add_argument( '--extras', action='store_true', help="If set, only 'extra' titles will be ripped" )


    args = parser.parse_args()
    mp.set_start_method('spawn')

    STREAM.setLevel( args.loglevel )
    LOG.addHandler(STREAM)
    watchdog( args.outdir, everything=args.all, extras=args.extras )
