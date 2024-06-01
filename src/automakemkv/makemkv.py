"""
Utilities for running MakeMKV

"""

import logging
import os
import re
import gzip

from threading import Thread
from subprocess import Popen, PIPE, STDOUT

from PyQt5 import QtCore

#from . import TEST_DATA_FILE, DBDIR
from .mkv_lookup import AP
from .mediaInfo import utils

SPLIT = re.compile( r'(".*?"|[^,]+)' )


def makemkvcon( command, *args, **opts ):
    """
    Run the makemkvcon command

    """

    log = logging.getLogger(__name__)

    if command not in ('info', 'mkv', 'backup', 'f', 'reg'):
        log.error( "Unsupported command : '%s'". command )
        return False

    cmd = ['makemkvcon', command]
    for key, val in opts.items():
        kkey = f"--{key}"
        if key in ('noscan', 'decrypt', 'robot'):
            if val is True: cmd.append( kkey )
        else:
            if isinstance(val, bool):
                val = str(val).lower()
            cmd.extend( [kkey, str(val)] )
    cmd.extend( args )

    log.debug( "Running command : %s", ' '.join(cmd))
    return Popen(
        cmd,
        universal_newlines = True,
        stdout = PIPE,
        stderr = STDOUT
    )


class MakeMKVParser:
    """
    Class to parse makemkvcon output

    Parses the robot output of MakeMKV to determine what titles/tracks have what
    information

    """

    def __init__(self, discDev='/dev/sr0', dbdir=None, **kwargs):
        super().__init__()

        self._debug = kwargs.get('debug', False)
        self.disc_dev = discDev
        self.info_path = utils.info_path(discDev, dbdir=dbdir)
        self.discInfo = {}
        self.titles = {}
        self.log = logging.getLogger(__name__).debug
        self.proc = None

    def loadFile(self, json=None):
        """
        Load stored MakeMKV robot output

        """

        self.titles = {}
        if json is None:
            fpath = self.info_path
        else:
            fpath = os.path.splitext(json)[0]+'.info.gz'

        with gzip.open(fpath, 'rt') as iid:
            for line in iid.readlines():
                self.parse_line(line)

    def scanDisc(self):
        """
        Run scan on a disc

        """

        if self.info_path is None:
            return

        # Start scanning disc
        self.proc = makemkvcon(
            'info',
            f'dev:{self.disc_dev}',
            minlength=0,
            robot=True,
        )

        # Open gzip file for storing robot output and write MakeMKV output to file
        with gzip.open(self.info_path, 'wt') as fid:
            for line in iter(self.proc.stdout.readline, ''):
                fid.write(line)
                self.parse_line(line)
        self.proc.wait()

    def parse_line( self, line ):
        """Parse lines from makemkvcon"""

        infoType, *data = line.strip().split(':')
        data = ':'.join( data )

        if infoType == 'MSG':
            _, _, _, val, *_ = SPLIT.findall( data )
            self.log(val.strip('"'))
        elif infoType == 'CINFO':
            cid, _, val = SPLIT.findall( data )
            if cid in AP:
                self.discInfo[ AP[cid] ] = val.strip('"')
        elif infoType == 'TINFO':
            title, tid, _, val = SPLIT.findall( data )
            if title not in self.titles:
                self.titles[title] = {'streams' : {}}
            if tid in AP:
                self.titles[title][ AP[tid] ] = val.strip('"')
        elif infoType == 'SINFO':
            title, stream, sid, _, val = SPLIT.findall( data )
            tt = self.titles[title]['streams']
            if stream not in tt:
                tt[stream] = {}
            if sid in AP:
                tt[stream][ AP[sid] ] = val.strip('"')

    def kill(self):
        """Attempt to kill MakeMKV scan subprocess"""

        self.log('Attempting to kill process')
        if self.proc is None:
            return
        if self.proc.poll() is not None:
            self.log('Process already finished')
            return
        self.log('Killing process')
        self.proc.kill()


class MakeMKVThread(MakeMKVParser, QtCore.QThread):
    """
    Class to parse makemkvcon output
    """

    signal = QtCore.pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.log = self.signal.emit

    def run(self):
        """
        Run as separate thread

        This thread will start the makemkvcon process
        and iterate over the output from the command 
        line by line, parsing each line.

        Message lines are put on a Queue() object so
        that GUI is updated as scanning disc.
        Title/stream information is parsed and appended
        to a dictionary for later use.

        """

        self.scanDisc()


class MakeMKVConLog(Thread):
    """
    Run makemkvcron and log output

    Run the makemkvcron CLI and pipe all stdout/stderr data to python log

    """

    def __init__(self, command, *args, **opts):
        super().__init__()
        self.log = logging.getLogger(__name__)
        self.command = command
        self.args = args
        self.opts = opts
        self.proc = None

    @property
    def returncode(self):
        """Get returncode from processs"""

        if self.proc:
            return self.proc.returncode
        return None

    def run(self):
        """Method to run in thread"""

        self.proc = makemkvcon(self.command, *self.args, **self.opts)
        for line in iter(self.proc.stdout.readline, ''):
            self.log.info(
                "[%s] %s",
                " - ".join(self.args),
                line.rstrip(),
            )
        self.proc.communicate()
        self.log.info("MakeMKVConLog thread dead")

    def kill(self):
        """Kill the MakeMKV Process"""

        if self.proc:
            self.log.info('Killing process')
            self.proc.kill()
