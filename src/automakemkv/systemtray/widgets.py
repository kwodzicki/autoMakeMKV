import logging
import os

from PyQt5.QtWidgets import (
    QFileDialog,
    QWidget,
    QDialog,
    QDialogButtonBox,
    QRadioButton,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
)

from .utils import load_settings, save_settings


class MissingOutdirDialog(QDialog):
    def __init__(self, outdir):
        super().__init__()

        self.setWindowTitle("autoMakeMKV: Output Directory Missing!")

        QBtn = QDialogButtonBox.Ok | QDialogButtonBox.Abort

        self.buttonBox = QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.layout = QVBoxLayout()
        message = (
            "Could not find the requested output directory: ",
            os.linesep,
            outdir,
            os.linesep,
            "Would you like to select a new one?",
        )
        message = QLabel(
            os.linesep.join(message)
        )
        self.layout.addWidget(message)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)


class SettingsWidget(QDialog):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.dbdir = PathSelector('Database Location:')
        self.outdir = PathSelector('Output Location:')

        radio_layout = QVBoxLayout()
        self.features = QRadioButton("Only Features")
        self.extras = QRadioButton("Only Extras")
        self.everything = QRadioButton("All Titles")
        radio_layout.addWidget(self.features)
        radio_layout.addWidget(self.extras)
        radio_layout.addWidget(self.everything)
        radio_widget = QWidget()
        radio_widget.setLayout(radio_layout)

        self.set_settings()

        buttons = QDialogButtonBox.Save | QDialogButtonBox.Cancel
        button_box = QDialogButtonBox(buttons)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(self.dbdir)
        layout.addWidget(self.outdir)
        layout.addWidget(radio_widget)
        layout.addWidget(button_box)
        self.setLayout(layout)

    def set_settings(self):

        settings = load_settings()
        self.features.setChecked(True)
        if 'dbdir' in settings:
            self.dbdir.setText(settings['dbdir'])
        if 'outdir' in settings:
            self.outdir.setText(settings['outdir'])
        if 'everything' in settings:
            self.everything.setChecked(settings['everything'])
        if 'extras' in settings:
            self.extras.setChecked(settings['extras'])

    def get_settings(self):

        settings = {
            'dbdir': self.dbdir.getText(),
            'outdir': self.outdir.getText(),
            'extras': self.extras.isChecked(),
            'everything': self.everything.isChecked(),
        }
        save_settings(settings)
        return settings


class PathSelector(QWidget):

    def __init__(self, label, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.__log = logging.getLogger(__name__)
        self.path = None

        self.path_text = QLineEdit()
        self.path_button = QPushButton('Select Path')
        self.path_button.clicked.connect(self.path_select)

        layout = QHBoxLayout()
        layout.addWidget(self.path_text)
        layout.addWidget(self.path_button)
        widget = QWidget()
        widget.setLayout(layout)

        layout = QVBoxLayout()
        layout.addWidget(QLabel(label))
        layout.addWidget(widget)

        self.setLayout(layout)

    def setText(self, var):

        self.path_text.setText(var)

    def getText(self):

        return self.path_text.text()

    def path_select(self, *args, **kwargs):

        path = QFileDialog.getExistingDirectory(self, 'Select Folder')
        if path != '' and os.path.isdir(path):
            self.setText(path)
            self.__log.info(path)
