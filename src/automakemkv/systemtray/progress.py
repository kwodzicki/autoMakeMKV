import logging
import os

from PyQt5.QtWidgets import (
    QWidget,
    QProgressBar,
    QLabel,
    QVBoxLayout,
    QGridLayout,
    QFrame,
)
from PyQt5.QtCore import QTimer, pyqtSlot, pyqtSignal
#from PyQt5.QtGui import QFrame

MEGABYTE = 10**6


class ProgressDialog(QWidget):
    ADD_DISC = pyqtSignal(str, dict)  # First arg in dev, second is all info
    REMOVE_DISC = pyqtSignal(str)  # Arg is dev of disc to remove
    CUR_TRACK = pyqtSignal(str, str)  # First arg is dev, second is track num
    TRACK_SIZE = pyqtSignal(str, int)  # First arg is dev, second is size of cur track

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.log = logging.getLogger(__name__)
        self.enabled = False

        self.widgets = {}
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.ADD_DISC.connect(self.add_disc)
        self.REMOVE_DISC.connect(self.remove_disc)
        self.CUR_TRACK.connect(self.cur_track)
        self.TRACK_SIZE.connect(self.track_size)

    def __len__(self):
        return len(self.widgets)

    @pyqtSlot(str, dict)
    def add_disc(self, dev: str, info: dict):
        self.log.debug("Adding disc: %s", dev)
        widget = ProgressWidget(dev, info)
        self.layout.addWidget(widget)
        self.widgets[dev] = widget
        self.show()

    @pyqtSlot(str)
    def remove_disc(self, dev: str):
        self.log.debug("Removing disc: %s", dev)
        widget = self.widgets.pop(dev, None)
        if widget is not None:
            self.layout.removeWidget(widget)
            self.widget.deleteLater()
        if len(self.widgets) == 0:
            self.setVisible(False)

    @pyqtSlot(str, str)
    def cur_track(self, dev: str, title: str):
        self.log.debug("Setting current track: %s - %s", dev, title)
        widget = self.widgets.get(dev, None)
        if widget is None:
            return
        widget.cur_track(title)

    @pyqtSlot(str, int)
    def track_size(self, dev, tsize):
        self.log.debug("Update current track size: %s - %d", dev, tsize)
        widget = self.widgets.get(dev, None)
        if widget is None:
            return
        widget.track_size(tsize)

        
class ProgressWidget(QFrame):
    """
    Progress for a single disc

    Notes:
        All sizes are converted from bytes (assumed input units) to megabytes
        to stay unders 32-bit integer range.

    """

    def __init__(self, dev, info):
        super().__init__()

        self.setFrameStyle(
            QFrame.StyledPanel | QFrame.Plain
        )
        self.setLineWidth(1)

        self.info = info
        self.cur_title = None
        self.n_titles = 0
        self.title_sizes = []
        tot_size = scale_mb(
            sum(t.get('size', 0) for t in info.values())
        )


        self.title = QLabel(f"Disc: {dev}") 
        self.track_label = QLabel('')
        self.track_count = QLabel('')
        self.track_prog = QProgressBar()

        self.disc_label = QLabel('Overall Progress')
        self.disc_prog = QProgressBar()
        self.disc_prog.setRange(0, tot_size)
        self.disc_prog.setValue(0)

        layout = QGridLayout()
        layout.addWidget(self.title, 0, 0, 1, 3)
        layout.addWidget(self.track_label, 10, 0)
        layout.addWidget(self.track_count, 10, 2)
        layout.addWidget(self.track_prog, 11, 0, 1, 3)
        layout.addWidget(self.disc_label, 20, 0, 1, 3)
        layout.addWidget(self.disc_prog, 21, 0, 1, 3)

        self.setLayout(layout)

    def __len__(self):
        return len(self.info)

    def cur_track(self, title: str):
        """
        Update current track index

        Change the currently-being-worked-on-track to a new track

        Arguments:
            title (str): Title number from disc being ripperd

        """

        # If the cur_title is not None, then refers to previously processed track and
        # must update the total size of that track to be maximum size of the track
        if self.cur_title is not None:
            self.title_sizes[-1] = scale_mb(
                self
                .info
                .get(self.cur_title, {})
                .get('size', 0)
            )

        # Increment number of titles processed and append file size
        self.n_titles += 1
        self.title_sizes.append(0)

        path = (
            self
            .info.get(title, {})
            .get('path', '')
        )
        self.track_label.setText(
            f"Outfile: {path}",
        )
        self.track_count.setText(
            f"Title: {self.n_titles}/{len(self)}",
        ) 

        # Update progress stats for new track
        self.track_prog.setRange(
            0,
            scale_mb(self.info.get(title, {}).get('size', 0)),
        )
        self.track_prog.setValue(0)
        self.cur_title = title

    def track_size(self, tsize):
        """
        Update track size progress

        Updat

        """

        if len(self.title_sizes) == 0:
            return

        self.title_sizes[-1] = tsize
        self.track_prog.setValue(
            scale_mb(tsize)
        )
        self.disc_prog.setValue(
            scale_mb(sum(self.title_sizes))
        )


def scale_mb(val):

    return val // MEGABYTE + 1
