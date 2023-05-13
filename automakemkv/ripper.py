"""
Utilities for ripping titles

"""

import logging
import os
import signal
import time
import subprocess
from multiprocessing import Process
from threading import Event

import pyudev

from . import UUID_ROOT
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

def watchdog( outdir, everything=False, extras=False, root=UUID_ROOT, fileGen=video_utils_outfile):
    """
    Main watchdog for disc monitoring/ripping

    This function will run a pyudev monitor instance,
    looking for changes in disc. On change, will
    spawn the getTitleInfo() function, loading
    information from the database if exists, or
    prompting using for information via a GUI.

    After information is obtained, a rip of the
    requested/flagged tracks will start.

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

    log     = logging.getLogger( __name__ )
    log.debug( "%s started", __name__ )

    mounted   = {}
    lastevent = {}
    context   = pyudev.Context()
    monitor   = pyudev.Monitor.from_netlink(context)
    monitor.filter_by(subsystem='block')
    while RUNNING.is_set():
        device = monitor.poll(timeout=1.0)
        if device is None:
            continue

        # Get value for KEY. If is None, then did not exist, so continue
        dev = device.properties.get(KEY, None)
        if dev is None:
            continue

        # If we did NOT change an insert/eject event
        if device.properties.get(CHANGE, None) is None:
            log.debug( 'Caught event that was NOT insert/eject, ignoring' )
            continue

        # If def is NOT in mounted, initialize to False
        if dev not in mounted:
            mounted[dev] = is_mounted( dev )
        else:
            mounted[dev] = not mounted[dev]

        if not mounted[dev]:
            log.info( 'Device has been ejected : %s', dev )
            continue

        Process(
            target = rip_disc,
            args   = (dev, root, outdir, everything, extras, fileGen),
        ).start()

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

def rip_disc( dev, root, outdir, everything, extras, fileGen ):
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

    info = getTitleInfo( dev, root )
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
