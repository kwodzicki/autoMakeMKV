import logging

from PyQt5 import QtWidgets
from PyQt5 import QtCore

from . import utils

MEGABYTE = 10**6


class ProgressDialog(QtWidgets.QWidget):

    # First arg in dev, second is all info
    ADD_DISC = QtCore.pyqtSignal(str, dict)
    # Arg is dev of disc to remove
    REMOVE_DISC = QtCore.pyqtSignal(str)
    # First arg is dev, second is track num
    CUR_TRACK = QtCore.pyqtSignal(str, str)
    # First arg is dev, second is size of cur track
    TRACK_SIZE = QtCore.pyqtSignal(str, int)
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

        self.ADD_DISC.connect(self.add_disc)
        self.REMOVE_DISC.connect(self.remove_disc)
        self.CUR_TRACK.connect(self.current_track)
        self.TRACK_SIZE.connect(self.track_size)

    def __len__(self):
        return len(self.widgets)

    @QtCore.pyqtSlot(str, dict)
    def add_disc(self, dev: str, info: dict):
        self.log.debug("%s - Disc added", dev)
        widget = ProgressWidget(dev, info)
        widget.CANCEL.connect(self.cancel)

        self.layout.addWidget(widget)
        self.widgets[dev] = widget
        self.show()
        self.adjustSize()

    @QtCore.pyqtSlot(str)
    def remove_disc(self, dev: str):
        self.log.debug("%s - Disc removed", dev)
        widget = self.widgets.pop(dev, None)
        if widget is not None:
            self.layout.removeWidget(widget)
            widget.deleteLater()
        if len(self.widgets) == 0:
            self.setVisible(False)
        self.adjustSize()

    @QtCore.pyqtSlot(str, str)
    def current_track(self, dev: str, title: str):
        self.log.debug("%s - Setting current track: %s", dev, title)
        widget = self.widgets.get(dev, None)
        if widget is None:
            return
        widget.current_track(title)

    @QtCore.pyqtSlot(str, int)
    def track_size(self, dev, tsize):
        self.log.debug("%s - Update current track size: %d", dev, tsize)
        widget = self.widgets.get(dev, None)
        if widget is None:
            return
        widget.track_size(tsize)

    @QtCore.pyqtSlot(str)
    def cancel(self, dev):
        self.CANCEL.emit(dev)
        self.REMOVE_DISC.emit(dev)


class ProgressWidget(QtWidgets.QFrame):
    """
    Progress for a single disc

    Notes:
        All sizes are converted from bytes (assumed input units) to megabytes
        to stay unders 32-bit integer range.

    """

    CANCEL = QtCore.pyqtSignal(str)  # dev to cancel rip of

    def __init__(self, dev, info):
        super().__init__()

        self.setFrameStyle(
            QtWidgets.QFrame.StyledPanel | QtWidgets.QFrame.Plain
        )
        self.setLineWidth(1)

        self.n_titles = 0
        self.title_sizes = []
        self.current_title = None
        self.dev = dev
        self.info = info
        tot_size = 100 * len(info['titles'])

        vendor, model = utils.get_vendor_model(dev)
        self.drive = QtWidgets.QLabel(
            f"Device: {vendor} {model} [{dev}]",
        )

        self.metadata = Metadata()

        self.track_prog = QtWidgets.QProgressBar()
        self.track_prog.setRange(0, 100)

        self.disc_label = QtWidgets.QLabel('Overall Progress')
        self.disc_prog = QtWidgets.QProgressBar()
        self.disc_prog.setRange(0, tot_size)
        self.disc_prog.setValue(0)

        self.cancel_but = QtWidgets.QPushButton("Cancel Rip")
        self.cancel_but.clicked.connect(self.cancel)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.drive)
        layout.addWidget(self.metadata)
        layout.addWidget(self.track_prog)
        layout.addWidget(self.disc_label)
        layout.addWidget(self.disc_prog)
        layout.addWidget(self.cancel_but)

        self.setLayout(layout)

    def __len__(self):
        return len(self.info)

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

        # If the current_title is not None, then refers to previously
        # processed track and must update the total size of that track
        # to be maximum size of the track
        if self.current_title is not None:
            self.title_sizes[-1] = 100
            self.track_size(100)

        info = self.info['titles'][title]
        self.metadata.update(info)

        # Increment number of titles processed and append file size
        self.n_titles += 1
        self.title_sizes.append(0)

        self.current_title = title
        self.track_size(0)

    def track_size(self, tsize):
        """
        Update track size progress

        Updat

        """

        if len(self.title_sizes) == 0:
            return

        self.title_sizes[-1] = tsize
        self.track_prog.setValue(tsize)
        self.disc_prog.setValue(
            sum(self.title_sizes)
        )


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
