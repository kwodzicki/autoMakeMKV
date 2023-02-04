import re

from threading import Event
from queue import Queue
from subprocess import Popen, PIPE, STDOUT

from PyQt5 import QtCore

from . import TEST_DATA_FILE
from .mkvLookup import AP

SPLIT = re.compile( r'(".*?"|[^,]+)' )

class MakeMKVParser( QtCore.QThread ):
    """
    Class to parse makemkvcon output
    """

    str_signal = QtCore.pyqtSignal(str)

    def __init__(self, discDev='/dev/sr0', debug=False):
        super().__init__()

        self._event  = Event()
        self._debug  = debug
        self.discDev = discDev
        self.titles  = {}

    def is_alive(self):

        return self._event.is_set()

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

        self._event.set()
        if self._debug:
            with open(TEST_DATA_FILE, 'r') as iid:
                for line in iid.readlines():
                    self.parseLine( line )
        else:
            proc = Popen( 
                ['makemkvcon', 'info', '-r', f'dev:{self.discDev}'],
                universal_newlines = True,
                stdout = PIPE,
                stderr = STDOUT
            )
            for line in iter(proc.stdout.readline, ''):
                self.parseLine( line )
            proc.wait()
        self._event.clear()

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
