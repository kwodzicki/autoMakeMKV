import os

from PyQt5.QtWidgets import (
    QDialog,
    QWidget,
    QProgressBar,
    QLabel,
    QVBoxLayout,
    QGridLayout,
)
from PyQt5.QtCore import QTimer, pyqtSlot, pyqtSignal


class StatusDialog(QDialog):
    ADD_DISC = pyqtSignal(str, dict)
    CUR_TRACK = pyqtSignal(str, str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.widgets = {}
        self.layout = QVBoxLayout()

        self.setLayout(self.layout)

        self.ADD_DISC.connect(self.add_disc)
        self.CUR_TRACK.connect(self.cur_track)
    def __len__(self):
        return len(self.widgets)

    @pyqtSlot(str, dict)
    def add_disc(self, dev, info):
        widget = StatusWidget(info)
        self.layout.addWidget(widget)
        self.widgets[dev] = widget


    @pyqtSlot(str, str)
    def cur_track(self, dev, title):
        pass

class StatusWidget(QWidget):

    def __init__(self, info):
        super().__init__():

        self.info = info
        self.cur_title = None
        self.n_titles = 0
        self.cur_tot_size = [0]*len(self)
        self.tot_size = sum(
            [t['size'] for t in info.values()]
        )

        self.track_label = QLabel('')
        self.track_count = QLabel('')
        self.track_prog = QProgressBar()

        self.disc_label = QLabel('')
        self.disc_prog = QProgressBar()
        self.disc_prog.setRange(0, self.tot_size)

        layout = QGridLayout()
        layout.addItem(self.track_label, 0, 0)
        layout.addItem(self.track_count, 0, 2)
        layout.addItem(self.track_prog, 1, 0, columnSpan=3)
        layout.addItem(self.disc_prog, 5, 0, columnSpan=3)
        layout.addItem(self.disc_prog, 6, 0, columnSpan=3)

        self.setLayout(layout)

    def __len__(self):
        return len(self.info)

    @pyqtSlot(str)
    def set_title(self, title):
        self.n_titles += 1
        self.track_label.setText(title)
        self.track_count.setText(f"{self.n_titles}/{len(self)}") 

        self.track_prog.setRange(0, self.info[title]['size'])
        if self.cur_title:
            self.cur_tot_size[self._cur_title] = self.info[title]['size']
        self.cur_title = title
