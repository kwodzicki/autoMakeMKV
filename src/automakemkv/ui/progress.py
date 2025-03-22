import logging
import time
from datetime import timedelta

import re
from threading import Lock
from subprocess import Popen

from PyQt5 import QtWidgets
from PyQt5 import QtCore

from . import utils

MEGABYTE = 10**6


class ProgressDialog(QtWidgets.QWidget):

    # First arg in dev, second is all info
    MKV_ADD_DISC = QtCore.pyqtSignal(str, dict, bool)
    # Arg is dev of disc to remove
    MKV_REMOVE_DISC = QtCore.pyqtSignal(str)
    # Args are dev of disc to attach process to, the Popen object, and the
    # pipe to read from
    MKV_NEW_PROCESS = QtCore.pyqtSignal(str, Popen, str)
    # First arg is dev, second is track num
    MKV_CUR_TRACK = QtCore.pyqtSignal(str, str)
    # First arg is dev, second is track num
    MKV_CUR_DISC = QtCore.pyqtSignal(str, str)
    # dev of the rip to cancel
    CANCEL = QtCore.pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.log = logging.getLogger(__name__)
        self.enabled = False

        self.setWindowFlags(
            self.windowFlags()
            & ~QtCore.Qt.WindowCloseButtonHint
        )

        self.widgets = {}
        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)

        self.MKV_ADD_DISC.connect(self.mkv_add_disc)
        self.MKV_REMOVE_DISC.connect(self.mkv_remove_disc)
        self.MKV_NEW_PROCESS.connect(self.mkv_new_process)
        self.MKV_CUR_TRACK.connect(self.mkv_current_track)

    def __len__(self):
        return len(self.widgets)

    @QtCore.pyqtSlot(str, dict, bool)
    def mkv_add_disc(self, dev: str, info: dict, full_disc: bool):
        self.log.debug("%s - Disc added", dev)
        widget = ProgressWidget(dev, info, full_disc)
        widget.CANCEL.connect(self.cancel)

        self.layout.addWidget(widget)
        self.widgets[dev] = widget
        self.show()
        self.adjustSize()

    @QtCore.pyqtSlot(str)
    def mkv_remove_disc(self, dev: str):
        widget = self.widgets.pop(dev, None)
        if widget is not None:
            self.layout.removeWidget(widget)
            widget.deleteLater()
            self.log.debug("%s - Disc removed", dev)

        if len(self.widgets) == 0:
            self.setVisible(False)
        self.adjustSize()

    @QtCore.pyqtSlot(str, Popen, str)
    def mkv_new_process(self, dev: str, proc: Popen, pipe: str):
        widget = self.widgets.get(dev, None)
        if widget is None:
            return
        self.log.debug("%s - Setting new parser process", dev)
        widget.NEW_PROCESS.emit(proc, pipe)

    @QtCore.pyqtSlot(str)
    def mkv_current_disc(self, dev: str):
        widget = self.widgets.get(dev, None)
        if widget is None:
            return

    @QtCore.pyqtSlot(str, str)
    def mkv_current_track(self, dev: str, title: str):
        widget = self.widgets.get(dev, None)
        if widget is None:
            return
        self.log.debug("%s - Setting current track: %s", dev, title)
        widget.current_track(title)

    @QtCore.pyqtSlot(str)
    def cancel(self, dev):
        self.CANCEL.emit(dev)
        self.MKV_REMOVE_DISC.emit(dev)


class BasicProgressWidget(QtWidgets.QWidget):
    """
    Progress for a single disc

    Notes:
        All sizes are converted from bytes (assumed input units) to megabytes
        to stay unders 32-bit integer range.

    """

    CANCEL = QtCore.pyqtSignal(str)  # dev to cancel rip of
    NEW_PROCESS = QtCore.pyqtSignal(Popen, str)

    def __init__(
        self,
        dev: str,
        proc: Popen | None = None,
        pipe: str | None = None,
    ):
        super().__init__()

        self.log = logging.getLogger(__name__)

        self._track_t = None
        self._disc_t = None
        self._track_frac = 0.0
        self._disc_frac = 0.0

        # Timer thread for running elapsed/remaining
        self._timer = QtCore.QTimer()
        self._timer.timeout.connect(self._time_update)
        self._timer.start(1000)

        self.dev = dev

        self.track_label = QtWidgets.QLabel('')
        self.track_time = QtWidgets.QLabel('')
        self.track_prog = QtWidgets.QProgressBar()

        self.disc_label = QtWidgets.QLabel('')
        self.disc_time = QtWidgets.QLabel('')
        self.disc_prog = QtWidgets.QProgressBar()

        # Set up some track progress label
        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self.track_label)
        layout.addStretch()
        layout.addWidget(self.track_time)
        track = QtWidgets.QWidget()
        track.setLayout(layout)

        # Set up some disc progress label
        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self.disc_label)
        layout.addStretch()
        layout.addWidget(self.disc_time)
        disc = QtWidgets.QWidget()
        disc.setLayout(layout)

        # Set up final layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(track)
        layout.addWidget(self.track_prog)
        layout.addWidget(disc)
        layout.addWidget(self.disc_prog)

        self.setLayout(layout)

        self.thread = ProgressParser(proc, pipe=pipe)
        self.thread.PROGRESS_TITLE.connect(self.label_update)
        self.thread.PROGRESS_VALUE.connect(self.progress_update)

        self.thread.start()

        self.NEW_PROCESS.connect(self.new_process)

    @QtCore.pyqtSlot(Popen, str)
    def new_process(self, proc: Popen, pipe: str):
        """
        Handler for new disc scan process

        Arguments:
            proc (Popen): Popen object of makemkvcon scan
            pipe (str): Not used; just input empty string

        """

        self.log.debug(
            "%s - Updating process for parsing progress",
            self.dev,
        )
        self.thread.update_proc_pipe(proc=proc, pipe=pipe)

    @QtCore.pyqtSlot(str, str)
    def label_update(self, mtype: str, text: str):

        tt = time.monotonic()
        if mtype == 'PRGC':
            self.track_label.setText(text)
            self._track_t = tt
        elif mtype == 'PRGT':
            self.disc_label.setText(text)
            self._disc_t = tt

    @QtCore.pyqtSlot(int, int, int)
    def progress_update(self, current: int, total: int, maximum: int):

        if maximum == -1:
            self.track_prog.setValue(self.track_prog.maximum())
            self.disc_prog.setValue(self.disc_prog.maximum())
            return

        self.track_prog.setMaximum(maximum)
        self.track_prog.setValue(current)
        self._track_frac = current / maximum

        self.disc_prog.setMaximum(maximum)
        self.disc_prog.setValue(total)
        self._disc_frac = total / maximum

    def close(self, *args, **kwargs):
        """Overload to ensure timer thread stopped"""

        self._timer.stop()
        super().close(*args, **kwargs)

    def _time_update(self):
        """
        Timer thread for time-progress updated

        """

        cur_time = time.monotonic()
        self._time_update_sub(
            self._track_t,
            cur_time,
            self._track_frac,
            self.track_time,
        )

        self._time_update_sub(
            self._disc_t,
            cur_time,
            self._disc_frac,
            self.disc_time,
        )

    def _time_update_sub(
        self,
        ref_time: float | None,
        cur_time: float,
        frac: float,
        label: QtWidgets.QProgressBar,
    ) -> None:
        """
        Sub routine for time label update

        """

        if ref_time is None:
            return

        elapsed = cur_time - ref_time
        if elapsed < 5:
            label.setText("")
            return

        text = []
        if elapsed >= 10:
            remain = timedelta(
                seconds=round(
                    (elapsed / frac) - elapsed
                )
            )
            text.append(f"Remaining: {remain}")

        elapsed = timedelta(seconds=round(elapsed))
        text.append(f"Elapsed: {elapsed}")
        label.setText(" / ".join(text))


class ProgressWidget(QtWidgets.QFrame):
    """
    Progress for a single disc

    Notes:
        All sizes are converted from bytes (assumed input units) to megabytes
        to stay unders 32-bit integer range.

    """

    CANCEL = QtCore.pyqtSignal(str)  # dev to cancel rip of
    NEW_PROCESS = QtCore.pyqtSignal(Popen, str)

    def __init__(
        self,
        dev: str,
        info: dict,
        full_disc: bool,
        proc: Popen | None = None,
    ):
        super().__init__()

        self.log = logging.getLogger(__name__)

        self.setFrameStyle(
            QtWidgets.QFrame.StyledPanel | QtWidgets.QFrame.Plain
        )
        self.setLineWidth(1)

        self.n_titles = 0
        self.current_title = None
        self.dev = dev
        self.info = info

        vendor, model = utils.get_vendor_model(dev)
        self.drive = QtWidgets.QLabel(
            f"Device: {vendor} {model} [{dev}]",
        )

        if full_disc:
            self.metadata = QtWidgets.QLabel("Full Disc Backup")
        else:
            self.metadata = Metadata()

        self.progress = BasicProgressWidget(dev, proc=proc)
        self.NEW_PROCESS.connect(
            self.new_process
        )

        self.cancel_but = QtWidgets.QPushButton("Cancel Rip")
        self.cancel_but.clicked.connect(self.cancel)

        layout = QtWidgets.QGridLayout()
        layout.addWidget(self.drive, 0, 0)
        layout.addWidget(self.metadata, 5, 0)
        layout.addWidget(self.progress, 10, 0)
        layout.addWidget(self.cancel_but, 15, 0)

        self.setLayout(layout)

    def __len__(self):
        return len(self.info)

    @QtCore.pyqtSlot(Popen, str)
    def new_process(self, proc: Popen, pipe: str):
        self.log.debug(
            "%s - Creating new basic widget",
            self.dev,
        )

        layout = self.layout()
        layout.removeWidget(self.progress)
        self.progress.close()

        self.progress = BasicProgressWidget(self.dev, proc=proc, pipe=pipe)

        layout.addWidget(self.progress, 10, 0)

    def cancel(self, *args, **kwargs):

        message = QtWidgets.QMessageBox()
        res = message.question(
            self,
            '',
            "Are you sure you want to cancel the rip?",
            message.Yes | message.No,
        )
        if res == message.Yes:
            self.CANCEL.emit(self.dev)

    def current_track(self, title: str):
        """
        Update current track index

        Change the currently-being-worked-on-track to a new track

        Arguments:
            title (str): Title number from disc being ripperd

        """

        info = self.info.get('titles', {}).get(title, None)
        if info is None:
            return

        self.metadata.update(info)

        # Increment number of titles processed and append file size
        self.n_titles += 1
        self.current_title = title


class Metadata(QtWidgets.QWidget):

    def __init__(self):
        super().__init__()

        self.title = BaseLabel('Title')
        self.year = BaseLabel('Year')
        self.series = BaseLabel('Series')
        self.season = BaseLabel('Season')
        self.episode = BaseLabel('Episode')
        self.extra = BaseLabel('Extra')

        self._idx = -1
        self._layout = QtWidgets.QGridLayout()
        self.setLayout(self._layout)

    @property
    def idx(self):
        self._idx += 1
        return self._idx

    def update(self, info):

        self.clear()
        if info['isMovie']:
            self.is_movie(info)
        elif info['isSeries']:
            self.is_series(info)

        extra_type = info.get('extra', '')
        if extra_type == '':
            return

        extra = info.get('extraTitle', '')
        if extra == '':
            return

        self.extra.setText(
            f"{extra_type.title()}: {extra}"
        )
        self.extra.addToLayout(self._layout, self.idx)

    def is_movie(self, info: dict):

        self.title.setText(info['title'])
        self.year.setText(info['year'])

        self.title.addToLayout(self._layout, self.idx)
        self.year.addToLayout(self._layout, self.idx)

    def is_series(self, info: dict):

        self.series.setText(info['title'])
        self.year.setText(info['year'])
        self.title.setText(info['episodeTitle'])
        self.season.setText(info['season'])
        self.episode.setText(info['episode'])

        self.series.addToLayout(self._layout, self.idx)
        self.year.addToLayout(self._layout, self.idx)
        self.title.addToLayout(self._layout, self.idx)
        self.season.addToLayout(self._layout, self.idx)
        self.episode.addToLayout(self._layout, self.idx)

    def clear(self):
        self._idx = -1
        for i in reversed(range(self._layout.count())):
            widget = self._layout.itemAt(i).widget()
            self._layout.removeWidget(widget)
            widget.setParent(None)


class ProgressParser(QtCore.QThread):
    """
    Parse MakeMKV progress messages in thread

    """

    PROGRESS_TITLE = QtCore.pyqtSignal(str, str)
    PROGRESS_VALUE = QtCore.pyqtSignal(int, int, int)

    def __init__(
        self,
        proc: Popen | None = None,
        pipe: str | None = None,
    ):
        super().__init__()
        self.log = logging.getLogger(__name__)
        self.t0 = None
        self._lock = Lock()
        self._proc = proc
        self._pipe = pipe or 'stdout'

    @property
    def proc(self):
        with self._lock:
            return self._proc

    @property
    def pipe(self):
        with self._lock:
            return self._pipe

    def run(self):

        while self.proc is None or self.proc.poll() is None:
            if self.proc is None:
                time.sleep(0.5)
                continue

            pipe = getattr(self.proc, self.pipe, None)
            if pipe is None:
                continue

            if self.t0 is None:
                self.t0 = time.monotonic()

            try:
                line = pipe.readline()
            except Exception:
                continue

            cli = self.proc.args[0]
            if cli == 'makemkvcon':
                self.parse_makemkvcon(line)
            elif cli == 'mkvmerge':
                self.parse_mkvmerge(line)
            else:
                self.log.error("Parser not implemented for: %s", cli)

        self.PROGRESS_VALUE.emit(-1, -1, -1)
        self.log.debug("Progress processor thread dead")

    def update_proc_pipe(self, proc=None, pipe=None):
        with self._lock:
            if proc is not None:
                self._proc = proc
            if pipe is not None:
                self._pipe = pipe

    def parse_makemkvcon(self, line):
        """
        Parse information from makemkvcon

        """

        mtype, *vals = line.split(':')
        vals = ":".join(vals).split(',')

        if mtype == 'PRGV':
            current, total, maximum = map(int, vals)
            self.PROGRESS_VALUE.emit(current, total, maximum)
            return

        self.PROGRESS_TITLE.emit(
            mtype,
            vals[-1].rstrip().strip('"'),
        )

    def parse_mkvmerge(self, line):
        mm = re.search(r'Progress:\s*(\d+)%', line)
        if not mm:
            return
        prog = int(mm.group(1))
        self.PROGRESS_VALUE.emit(prog, prog, 100)


class BaseLabel(QtWidgets.QWidget):

    def __init__(self, label):
        super().__init__()

        self.label = QtWidgets.QLabel(f"{label}:")
        self.value = QtWidgets.QLabel('')

    def addToLayout(self, layout: QtWidgets.QGridLayout, row: int):

        layout.addWidget(self.label, row, 0)
        layout.addWidget(self.value, row, 1)

    def setText(self, text):
        self.value.setText(text)
