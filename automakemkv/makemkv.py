import logging
import os, re, tempfile

from queue import Queue
from subprocess import Popen, PIPE, STDOUT

from PyQt5 import QtCore

from . import TEST_DATA_FILE, DBDIR
from .mkvLookup import AP
from .mediaInfo.utils import infoPath

SPLIT = re.compile( r'(".*?"|[^,]+)' )

def makeMKV( command, *args, **opts ):
    log = logging.getLogger(__name__)

    if command not in ('info', 'mkv', 'backup', 'f', 'reg'):
        log.error( f"Unsupported command : '{command}'" )
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

    return Popen(
        cmd,
        universal_newlines = True,
        stdout = PIPE,
        stderr = STDOUT
    )

class MakeMKVParser( object ):
    """
    Class to parse makemkvcon output
    """

    def __init__(self, discDev='/dev/sr0', **kwargs):
        super().__init__()

        self._debug   = kwargs.get('debug', False)
        self.discDev  = discDev
        self.infoPath = infoPath( discDev )
        self.titles   = {}

    def loadFile(self, json=None):

        self.titles = {}
        if json is None:
            fpath = self.infoPath
        else:
            fpath = os.path.splitext(json)[0]+'.info'
        with open(fpath, 'r') as iid:
            for line in iid.readlines():
                self.parseLine( line )

    def scanDisc(self):

        if self.infoPath is None:
            return
        proc = makeMKV('info', f'dev:{self.discDev}', minlength=0, robot=True)
        with open( self.infoPath, 'w' ) as fid:
            for line in iter(proc.stdout.readline, ''):
                fid.write( line )
                self.parseLine( line )
        proc.wait()

    def parseLine( self, line ):
        """Parse lines from makemkvcon"""

        try:
            infoType, data = line.strip().split(':')
        except:
            return

        if infoType == 'MSG':
            _, _, _, val, *_ = SPLIT.findall( data )
            self.str_signal.emit( val.strip('"') )
        elif infoType == 'TINFO':
            title, tid, code, val = SPLIT.findall( data )
            if title not in self.titles:
                self.titles[title] = {'streams' : {}}
            if tid in AP:
                self.titles[title][ AP[tid] ] = val.strip('"')
        elif infoType == 'SINFO':
            title, stream, sid, code, val = SPLIT.findall( data )
            tt = self.titles[title]['streams']
            if stream not in tt:
                tt[stream] = {}
            if sid in AP:
                tt[stream][ AP[sid] ] = val.strip('"')

class MakeMKVThread( MakeMKVParser, QtCore.QThread ):
    """
    Class to parse makemkvcon output
    """

    str_signal = QtCore.pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

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
