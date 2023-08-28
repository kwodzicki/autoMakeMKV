"""
Utilities for ripping titles

"""

import logging
import os
import signal
import time
import subprocess
from multiprocessing import Process
from threading import Thread, Event

import pyudev

from . import UUID_ROOT, DBDIR
from .mediaInfo import getTitleInfo
from .makemkv import makemkvcon
from .utils import video_utils_outfile

KEY     = 'DEVNAME'
CHANGE  = 'DISK_MEDIA_CHANGE'
TIMEOUT = 10.0

RUNNING = Event()
RUNNING.set()

signal.signal( signal.SIGINT,  lambda *args : RUNNING.clear() )
signal.signal( signal.SIGTERM, lambda *args : RUNNING.clear() )

class RipperWatchdog(Thread):
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

    def __init__(self, outdir, everything=False, extras=False, root=UUID_ROOT, fileGen=video_utils_outfile, **kwargs):
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
        self.__log     = logging.getLogger( __name__ )
        self.__log.debug( "%s started", __name__ )
    
        self._outdir = None

        self.dbdir      = kwargs.get('dbdir', DBDIR)
        self.outdir     = outdir
        self.everything = everything
        self.extras     = extras
        self.root       = root
        self.fileGen    = fileGen

        self._mounting  = []
        self._mounted   = []
        self._context   = pyudev.Context()
        self._monitor   = pyudev.Monitor.from_netlink(self._context)
        self._monitor.filter_by(subsystem='block')

    @property
    def outdir(self):
        return self._outdir
    @outdir.setter
    def outdir(self, val):
        os.makedirs(val, exist_ok=True)
        self.__log.info('Output directory set to : %s', val)
        self._outdir = val

    def set_settings(self, **kwargs):
        """
        Set options for ripping discs

        """

        self.__log.debug('Updating ripping options')
        self.dbdir      = kwargs.get('dbdir',      self.dbdir)
        self.outdir     = kwargs.get('outdir',     self.outdir)
        self.everything = kwargs.get('everything', self.everything)
        self.extras     = kwargs.get('extras',     self.extras)

    def run(self):

        self.__log.info('Watchdog thread started')
        while RUNNING.is_set():
            device = self._monitor.poll(timeout=1.0)
            if device is None:
                continue

            # Get value for KEY. If is None, then did not exist, so continue
            dev = device.properties.get(KEY, None)
            if dev is None:
                continue

            # If we did NOT change an insert/eject event
            if device.properties.get(CHANGE, None) is None:
                if dev not in self._mounting:
                    self.__log.debug( 'Caught event that was NOT insert/eject, ignoring : %s', dev )
                    continue
                self.__log.debug('Finished mounting : %s', dev )
                self._mounting.remove( dev )
                self._mounted.append( dev )
                Process(
                    target = rip_disc,
                    args   = (dev, self.root, self.outdir, self.everything, self.extras, self.fileGen),
                    kwargs = {'dbdir' : self.dbdir},
                ).start()
                continue

            # If def is NOT in mounted, initialize to False
            if dev not in self._mounted:
                self.__log.info( 'Device is mounting : %s', dev )
                self._mounting.append( dev )
            else:
                self._mounted.remove(dev)
                self.__log.info( 'Device has been ejected : %s', dev )
        self.__log.info('Watchdog thread dead')

def is_mounted( dev ):
    """
    Check if disc is mounted

    """

    returncode = subprocess.run(
        ['file', '-s', dev],
        stdout = subprocess.DEVNULL,
        stderr = subprocess.STDOUT,
    ).returncode

    return returncode == 0

def rip_disc( dev, root, outdir, everything, extras, fileGen, dbdir=None ):
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

    log = logging.getLogger(__name__)

    info = getTitleInfo( dev, root, dbdir=dbdir )
    if info is None:
        log.error( "No title information found/entered : %s", dev )
        return

    if info != 'skiprip':
        for title, fpath in fileGen(outdir, info, everything=everything, extras=extras):
            rip_title( f"dev:{dev}", title, fpath )
    else:
        log.info( "Just saving metadata, not ripping : %s", dev )

    try:
        os.system( f"eject {dev}" )
    except:
        pass

def rip_title( src, title, outfile ):
    """
    Rip a given title from a disc

    Rip a title from the given disc to 
    a specific output file.

    Arguments:
        src (str) : Source disc
        title (str) : Title to rip
        outfile (str) : Name of the output file

    Returns:
        bool : True if ripped, False otherwise

    """

    log    = logging.getLogger(__name__)
    outdir = os.path.dirname( outfile )
    if not os.path.isdir( outdir ):
        os.makedirs( outdir )

    tmpdir = os.path.splitext( os.path.basename( outfile ) )[0]
    tmpdir = os.path.join( outdir, tmpdir )
    log.debug( "Creating temporary directory : '%s'", tmpdir )
    os.makedirs( tmpdir, exist_ok=True )

    baselog = f"[{src} - {title}]"
    log.info( "%s Ripping track", baselog )
    proc = makemkvcon('mkv', src, title, tmpdir, noscan=True, minlength=0)
    for line in iter(proc.stdout.readline, ''):
        log.info( "%s %s", baselog, line.rstrip() )
    proc.communicate()
    files = [
        os.path.join(tmpdir, item) for item in os.listdir(tmpdir)
    ]

    status = False
    if proc.returncode != 0:
        for fname in files:
            os.remove(fname)
        log.error( "Error ripping track '%s' from '%s'", title, src )
    elif len(files) != 1:
        log.error( 'Too many output files!' )
        for fname in files:
            os.remove( fname )
    else:
        log.info( "Renaming file '%s' ---> '%s'", files[0], outfile )
        os.rename( files[0], outfile )
        status = True

    os.rmdir( tmpdir )

    return status
