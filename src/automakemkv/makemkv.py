"""
Utilities for running MakeMKV

"""

import logging
import os
import re
import gzip

from subprocess import Popen, PIPE, STDOUT

from PyQt5 import QtCore

from .mkv_lookup import AP
from .mediaInfo import utils

SPLIT = re.compile(r'(".*?"|[^,]+)')


class MakeMKVThread(QtCore.QThread):
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

    def makemkvcon(self):
        """
        Run the makemkvcon command

        """

        if self.command not in ('info', 'mkv', 'backup', 'f', 'reg'):
            self.log.error("Unsupported command : '%s'", self.command)
            return

        cmd = ['makemkvcon', self.command]
        for key, val in self.opts.items():
            kkey = f"--{key}"
            if key in ('noscan', 'decrypt', 'robot'):
                if val is True:
                    cmd.append(kkey)
            else:
                if isinstance(val, bool):
                    val = str(val).lower()
                cmd.extend([kkey, str(val)])
        cmd.extend(self.args)

        self.log.debug("Running command : %s", ' '.join(cmd))
        self.proc = Popen(
            cmd,
            universal_newlines=True,
            stdout=PIPE,
            stderr=STDOUT,
        )

    def run(self):
        """Method to run in thread"""

        pass

    def quit(self):
        """Kill the MakeMKV Process"""

        if self.proc:
            self.log.info('Killing process')
            self.proc.kill()
        super().quit()


class MakeMKVRip(MakeMKVThread):

    def __init__(self, source: str, title: str, dest_folder: str, **kwargs):
        super().__init__(
            'mkv',  # Command set to mkv
            f"dev:{source}",  # Source: is dev
            title,
            dest_folder,
            **kwargs,
        )

    def run(self):

        self.makemkvcon()
        if self.proc is None:
            return

        for line in iter(self.proc.stdout.readline, ''):
            self.log.info(
                "[%s] %s",
                " - ".join(self.args),
                line.rstrip(),
            )
        self.proc.communicate()
        self.log.info("MakeMKVRip thread dead")


class MakeMKVInfo(MakeMKVThread):
    """
    Class to parse makemkvcon output

    Parses the robot output of MakeMKV to determine what titles/tracks
    have what information

    """

    signal = QtCore.pyqtSignal(str)

    def __init__(
        self,
        source: str = '/dev/sr0',
        dbdir: str | None = None,
        debug: bool = False,
        **kwargs,
    ):
        super().__init__(
            "info",
            f"dev:{source}",
            minlength=0,
            robot=True,
            **kwargs,
        )

        self._debug = debug
        self.info_path = utils.info_path(source, dbdir=dbdir)
        self.discInfo = {}
        self.titles = {}

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

        if self.info_path is None:
            return

        # Start scanning disc
        self.makemkvcon()

        # Open gzip file for storing robot output and write MakeMKV
        # output to file
        with gzip.open(self.info_path, 'wt') as fid:
            for line in iter(self.proc.stdout.readline, ''):
                fid.write(line)
                self.parse_line(line)
        self.proc.wait()

    def loadFile(self, json: str | None = None) -> None:
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

    def parse_line(self, line: str) -> None:
        """Parse lines from makemkvcon"""

        infoType, *data = line.strip().split(':')
        data = ':'.join(data)

        if infoType == 'MSG':
            _, _, _, val, *_ = SPLIT.findall(data)
            self.signal.emit(val.strip('"'))
        elif infoType == 'CINFO':
            cid, _, val = SPLIT.findall(data)
            if cid in AP:
                self.discInfo[AP[cid]] = val.strip('"')
        elif infoType == 'TINFO':
            title, tid, _, val = SPLIT.findall(data)
            if title not in self.titles:
                self.titles[title] = {'streams': {}}
            if tid in AP:
                self.titles[title][AP[tid]] = val.strip('"')
        elif infoType == 'SINFO':
            title, stream, sid, _, val = SPLIT.findall(data)
            tt = self.titles[title]['streams']
            if stream not in tt:
                tt[stream] = {}
            if sid in AP:
                tt[stream][AP[sid]] = val.strip('"')
