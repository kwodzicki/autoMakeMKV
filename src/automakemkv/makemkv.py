"""
Utilities for running MakeMKV

"""

import logging
import os
import re
import gzip

from threading import Event
from subprocess import (
    call,
    check_output,
    Popen,
    PIPE,
    TimeoutExpired,
    CalledProcessError,
)

from PyQt5 import QtCore

from . import DBDIR, MAKEMKVCON
from .utils import eject
from .mkv_lookup import AP

DEVICE_MSG = 'DRV:'
SANITIZE = (
    DEVICE_MSG,
    'MSG:1004',
    'MSG:2003',
    'MSG:3338',
)

SPLIT = re.compile(r'(".*?"|[^,]+)')
DEFAULT_KWARGS = {
    'robot': True,
    'noscan': True,
    'minlength': 0,
    'messages': '-stdout',
    'progress': '-stderr',
}

SWITCHES = ('noscan', 'robot', 'decrypt')
SOURCES = ('iso', 'file', 'disc', 'dev')
COMMANDS = ('info', 'mkv', 'backup', 'f', 'reg')
RESULTS_PREFIX = ("MSG:5004", "MSG:5037")


class MakeMKVThread(QtCore.QThread):
    """
    Run makemkvcron and log output

    Run the makemkvcron CLI and pipe all stdout/stderr data to python log

    """

    # Send the dev device that failed
    FAILURE = QtCore.pyqtSignal(str)
    SUCCESS = QtCore.pyqtSignal(str)

    def __init__(
        self,
        command: str,
        title: str | None = None,
        output: str | None = None,
        **opts,
    ):
        """
        iso: str | None = None,
        file: str | None = None,
        disc: str | None = None,
        dev: str | None = None,
        messages: str | None = None,
        progress: str | None = None,
        debug: str | bool | None = None,
        cache: int | None = None,
        minlength: int | None = None
        noscan: bool = False,
        robot: bool = False,
        decrypt: bool = False,
        directio: bool | None = None,

        """

        super().__init__()
        self.log = logging.getLogger(__name__)

        self._dev = None
        self._failure = False
        self._success = False

        self.started = Event()
        self.command = command
        self.source = self._parse_source(opts)
        self.title = title
        self.output = output
        self.opts = opts
        self.proc = None

    def _parse_source(self, opts):
        """
        Parse source and check is valid for command

        For the 'backup' command, the source must be 'disc'. So, we check
        here that were are using the disc id. If not, we can get the disc id
        from a dev device. Otherwise, have to throw and error

        """

        source = None
        for key in SOURCES:
            if key not in opts:
                continue

            if source is not None:
                self.log.warning(
                    "Multiple sources defined; assuming '%s:%s'",
                    *source,
                )
                _ = opts.pop(key)
                continue

            source = [key, opts.pop(key)]

        if source is None:
            self.log.error("No source defined!")
            self.command = None
            return source

        # Set dev device path here; folling clauses may return
        if source[0] == 'dev':
            self._dev = source[1]

        # If command is NOT backup or the type IS disc, then return source
        if self.command != 'backup' or source[0] == 'disc':
            return source

        # If made here and is NOT dev, then don't know what to do!
        if source[0] != 'dev':
            self.log.critical(
                "%s -  Cannot backup from '%s' device",
                source[1],
                source[0],
            )
            self.command = None
            return None

        # If here, try to look up disc number from dev
        lookup = _dev_to_disc()
        dev = source[1]
        if dev not in lookup:
            self.log.critical(
                "%s - Failed to find dev in disc list from makemkvcon",
                dev,
            )
            self.command = None
            return None

        return ['disc', lookup[dev]]

    def _check_type(self, source):
        if self.source is None:
            return False
        return self.source[0] == source

    @property
    def isiso(self):
        return self._check_type('iso')

    @property
    def isfile(self):
        return self._check_type('file')

    @property
    def isdisc(self):
        return self._check_type('disc')

    @property
    def isdev(self):
        return self._check_type('dev')

    @property
    def dev(self):
        return self._dev

    @dev.setter
    def dev(self, val):
        self._dev = val

    @property
    def returncode(self):
        """Get returncode from processs"""

        if self.proc:
            return self.proc.returncode
        return None

    @property
    def stdout(self):
        if self.proc is None:
            return None

        return self.proc.stdout

    @property
    def stderr(self):
        if self.proc is None:
            return None

        return self.proc.stderr

    def makemkvcon(self):
        """
        Run the makemkvcon command

        """

        if self.command is None:
            return

        if self.source is None:
            self.log.error("No source defined!")
            return

        opts = []
        for key, val in self.opts.items():
            if key in SWITCHES:
                if val is True:
                    opts.append(f"--{key}")
            else:
                if isinstance(val, bool):
                    val = str(val).lower()
                opts.append(f"--{key}={val}")

        # if self.command not in COMMANDS:
        #     self.log.error(
        #         "%s - Unsupported command : '%s'",
        #         self.source[1],
        #         self.command,
        #     )
        #     return

        cmd = [
            MAKEMKVCON,
            *opts,
            self.command,
            "{}:{}".format(*self.source),
        ]
        if self.title is not None:
            cmd.append(self.title)
        if self.output is not None:
            cmd.append(self.output)

        self.log.debug(
            "%s - Running command : %s",
            self.source[1],
            ' '.join(cmd),
        )

        self.proc = Popen(
            cmd,
            universal_newlines=True,
            stdout=PIPE,
            stderr=PIPE,
        )
        self.started.set()

    def run(self):
        """Method to run in thread"""

        pass

    def check_result(self, line: str) -> str:

        # If not a result-of-rip message, return line
        if not line.startswith(RESULTS_PREFIX):
            return line

        # If already determined success/failure, return line
        if self._success or self._failure:
            return line

        # Try to extact the number of success/failures from messages
        info = [val.strip().strip('"') for val in line.split(',')]
        try:
            success, failure = map(int, info[-2:])
        except Exception as err:
            self.log.debug(
                "%s - Failed to parse success/failure values: %s",
                self.source[1],
                err,
            )
            return line

        if failure > 0:
            self._failure = True
            self.log.error("%s - Rip failed", self.source[1])
            self.FAILURE.emit('{}:{}'.format(*self.source))
        elif success > 0:
            self._success = True
            self.log.error("%s - Rip success", self.source[1])
            self.SUCCESS.emit('{}:{}'.format(*self.source))
        else:
            self.log.warning(
                "%s - Ripped nothing; no success or failure reported",
                self.source[1],
            )
        return line

    def terminate(self):
        """Kill the MakeMKV Process"""

        if self.proc:
            self.log.info('Killing process')
            self.proc.kill()
        super().wait()


class MakeMKVRip(MakeMKVThread):

    def __init__(self, command: str, pipe: str | None = None, **kwargs):
        kwargs = {
            **DEFAULT_KWARGS,
            **kwargs,
        }

        super().__init__(command, **kwargs)
        self.pipe = pipe or 'stderr'

    def run(self):

        self.makemkvcon()
        if self.proc is None:
            return

        for line in iter(self.stdout.readline, ''):
            self.log.debug(
                "%s - %s",
                self.source[1],
                line.rstrip(),
            )
            self.check_result(line)
        self.proc.wait()
        self.proc.communicate()

        if self.dev is not None:
            self.log.debug("%s - Ejecting disc", self.dev)
            eject(self.dev)

        self.log.info("MakeMKVRip thread dead")


class MakeMKVInfo(MakeMKVThread):
    """
    Class to parse makemkvcon output

    Parses the robot output of MakeMKV to determine what titles/tracks
    have what information

    """

    SIGNAL = QtCore.pyqtSignal(str)

    def __init__(
        self,
        dev: str,
        discid: str,
        dbdir: str | None = None,
        **kwargs,
    ):
        kwargs = {
            **DEFAULT_KWARGS,
            **kwargs,
            'dev': dev,
        }

        super().__init__(
            "info",
            **kwargs,
        )

        self.dev = dev
        self.discid = discid
        self.info_path = os.path.join(
            dbdir or DBDIR,
            f"{discid}.info.gz",
        )

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

        self.log.debug("%s - Streaming data from stdout", self.dev)
        # Open gzip file for storing robot output and write MakeMKV
        # output to file
        with gzip.open(self.info_path, 'wt') as fid:
            for line in iter(self.stdout.readline, ''):
                fid.write(
                    sanitize(line)
                )
                self.parse_line(line)
                self.check_result(line)
        self.proc.wait()
        self.proc.communicate()

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
            self.SIGNAL.emit(val.strip('"'))
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
            # If title not in the titles object, then add emtpy dict
            if title not in self.titles:
                self.titles[title] = {}
            # If 'streams' not in title object, then add empty dict
            if 'streams' not in self.titles[title]:
                self.titles[title]['streams'] = {}

            # Get the 'streams' object for given title
            tt = self.titles[title]['streams']
            if stream not in tt:
                tt[stream] = {}
            if sid in AP:
                tt[stream][AP[sid]] = val.strip('"')


def sanitize(line: str) -> str:
    """
    Mask out sensitive information

    Masks out sensitive info in DRV messages and MSG 1004, 2003, 3338
    from MakeMKV.

    Issue #30 from TheDiscDb

    Arguments:
        line (str): Line from MakeMKV logs

    Returns:
        str: Sanititzed line from MakeMKV logs

    """

    if line.startswith(SANITIZE):
        return re.sub('"[^"]*"', '"***"', line)

    return line


def sanitize_database_file(path: str):
    """
    path (str): Path to database file to sanitize

    """

    # Read in all the data
    with gzip.open(path, mode='rt') as iid:
        lines = iid.readlines()

    # Write out sanitized data
    with gzip.open(path, mode='wt') as oid:
        for line in lines:
            oid.write(
                sanitize(line)
            )


def _dev_to_disc(timeout: float | int = 60.0) -> dict:
    """
    Get dict of dev devices to MakeMKV disc ids

    """

    log = logging.getLogger(__name__)

    output = {}
    try:
        info = check_output(
            [MAKEMKVCON, '--robot', '--noscan', 'info', 'disc'],
            timeout=timeout,
        )
    except TimeoutExpired as err:
        info = err.output
    except CalledProcessError as err:
        info = err.output
    except Exception as err:
        log.error("Failed to get disc ids from MakeMKV: %s", err)
        return output

    for line in info.decode().splitlines():
        if not line.startswith(DEVICE_MSG):
            continue
        info = line.strip(DEVICE_MSG).split(',')
        dev = info[-1].strip('"')
        if dev == '':
            continue
        output[dev] = info[0]

    return output
