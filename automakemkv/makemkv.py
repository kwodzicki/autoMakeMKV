"""
Utilities for running MakeMKV

"""

import logging
import os
import re
import gzip

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

class MakeMKVParser( ):
    """
    Class to parse makemkvcon output
    """

    def __init__(self, discDev='/dev/sr0', dbdir=None, **kwargs):
        super().__init__()

        self._debug    = kwargs.get('debug', False)
        self.disc_dev  = discDev
        self.info_path = utils.info_path( discDev, dbdir=dbdir )
        self.discInfo  = {}
        self.titles    = {}
        self.log       = logging.getLogger(__name__).debug

    def loadFile(self, json=None):

        self.titles = {}
        if json is None:
            fpath = self.info_path
        else:
            fpath = os.path.splitext(json)[0]+'.info.gz'
        with gzip.open(fpath, 'rt') as iid:
            for line in iid.readlines():
                self.parse_line( line )

    def scanDisc(self):

        if self.info_path is None:
            return
        proc = makemkvcon('info', f'dev:{self.disc_dev}', minlength=0, robot=True)
        with gzip.open( self.info_path, 'wt' ) as fid:
            for line in iter(proc.stdout.readline, ''):
                fid.write( line )
                self.parse_line( line )
        proc.wait()

    def parse_line( self, line ):
        """Parse lines from makemkvcon"""

        infoType, *data = line.strip().split(':')
        data = ':'.join( data )

        if infoType == 'MSG':
            _, _, _, val, *_ = SPLIT.findall( data )
            self.log( val.strip('"') )
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

class MakeMKVThread( MakeMKVParser, QtCore.QThread ):
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
