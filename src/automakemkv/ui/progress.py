import logging
import time

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
    # Args are dev of disc to attach process to and the process
    MKV_NEW_PROCESS = QtCore.pyqtSignal(str, Popen)
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

    @QtCore.pyqtSlot(str, Popen)
    def mkv_new_process(self, dev: str, proc: Popen):
        widget = self.widgets.get(dev, None)
        if widget is None:
            return
        self.log.debug("%s - Setting new parser process", dev)
        widget.NEW_PROCESS.emit(proc)

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
    NEW_PROCESS = QtCore.pyqtSignal(Popen)

    def __init__(self, dev: str, proc: Popen | None = None):
        super().__init__()

        self.log = logging.getLogger(__name__)

        self.dev = dev

        self.track_label = QtWidgets.QLabel('')
        self.track_prog = QtWidgets.QProgressBar()

        self.disc_label = QtWidgets.QLabel('')
        self.disc_prog = QtWidgets.QProgressBar()

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.track_label)
        layout.addWidget(self.track_prog)
        layout.addWidget(self.disc_label)
        layout.addWidget(self.disc_prog)

        self.setLayout(layout)

        self.thread = ProgressParser(proc)
        self.thread.PROGRESS_TITLE.connect(self.label_update)
        self.thread.PROGRESS_VALUE.connect(self.progress_update)

        self.thread.start()

        self.NEW_PROCESS.connect(self.new_process)

    @QtCore.pyqtSlot(Popen)
    def new_process(self, proc: Popen):

        self.log.debug(
            "%s - Updating process for parsing progress",
            self.dev,
        )
        self.thread.proc = proc

    @QtCore.pyqtSlot(str, str)
    def label_update(self, mtype: str, text: str):

        if mtype == 'PRGC':
            self.track_label.setText(text)
        elif mtype == 'PRGT':
            self.disc_label.setText(text)

    @QtCore.pyqtSlot(int, int, int)
    def progress_update(self, current: int, total: int, maximum: int):

        if maximum == -1:
            self.track_prog.setValue(self.track_prog.maximum())
            self.disc_prog.setValue(self.disc_prog.maximum())
            return

        self.track_prog.setMaximum(maximum)
        self.track_prog.setValue(current)
        self.disc_prog.setMaximum(maximum)
        self.disc_prog.setValue(total)


class ProgressWidget(QtWidgets.QFrame):
    """
    Progress for a single disc

    Notes:
        All sizes are converted from bytes (assumed input units) to megabytes
        to stay unders 32-bit integer range.

    """

    CANCEL = QtCore.pyqtSignal(str)  # dev to cancel rip of
    NEW_PROCESS = QtCore.pyqtSignal(Popen)

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
            # self.progress.new_process
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

    @QtCore.pyqtSlot(Popen)
    def new_process(self, proc: Popen):
        self.log.debug(
            "%s - Creating new basic widget",
            self.dev,
        )

        layout = self.layout()
        layout.removeWidget(self.progress)
        self.progress.close()

        self.progress = BasicProgressWidget(self.dev, proc=proc)

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

        info = self.info['titles'][title]
        print(info)
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

        self._layout = QtWidgets.QGridLayout()
        self.setLayout(self._layout)

    def update(self, info):

        self.clear()
        if info['isMovie']:
            self.is_movie(info)
        elif info['isSeries']:
            self.is_series(info)

    def is_movie(self, info):

        self.title.setText(info['title'])
        self.year.setText(info['year'])

        self.title.addToLayout(self._layout, 0)
        self.year.addToLayout(self._layout, 1)

    def is_series(self, info):

        self.series.setText(info['title'])
        self.year.setText(info['year'])
        self.title.setText(info['episodeTitle'])
        self.season.setText(info['season'])
        self.episode.setText(info['episode'])

        self.series.addToLayout(self._layout, 0)
        self.year.addToLayout(self._layout, 1)
        self.title.addToLayout(self._layout, 2)
        self.season.addToLayout(self._layout, 3)
        self.episode.addToLayout(self._layout, 4)

    def clear(self):

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

    def __init__(self, proc: Popen | None = None, pipe: str = 'stderr'):
        super().__init__()
        self.log = logging.getLogger(__name__)
        self.proc = proc
        self.pipe = pipe
        self.t0 = None

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

            mtype, *vals = line.split(':')
            vals = ":".join(vals).split(',')

            if mtype == 'PRGV':
                current, total, maximum = map(int, vals)
                self.PROGRESS_VALUE.emit(current, total, maximum)
                continue

            self.PROGRESS_TITLE.emit(
                mtype,
                vals[-1].rstrip().strip('"'),
            )

        self.PROGRESS_VALUE.emit(-1, -1, -1)
        self.log.debug("Progress processor thread dead")


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
