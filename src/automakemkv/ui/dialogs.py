import os

from PyQt5 import QtWidgets
from PyQt5 import QtCore

from .. import NAME
from ..path_utils import CONVENTIONS
from . import utils
from . import widgets


class MissingDirDialog(QtWidgets.QDialog):
    def __init__(self, outdir: str, dtype: str, name: str = NAME):
        super().__init__()

        self._name = name
        self.setWindowTitle(f"{self._name}: {dtype} Directory Missing!")

        QBtn = QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Abort

        self.buttonBox = QtWidgets.QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.layout = QtWidgets.QVBoxLayout()
        message = (
            "Could not find the requested output directory: ",
            os.linesep,
            outdir,
            os.linesep,
            "Would you like to select a new one?",
        )
        message = QtWidgets.QLabel(
            os.linesep.join(message)
        )
        self.layout.addWidget(message)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)


class RipFailure(QtWidgets.QDialog):

    def __init__(self, device: str, name: str = NAME):
        super().__init__()

        self._name = name
        self.setWindowTitle(f"{self._name}: Rip Failed!")

        QBtn = QtWidgets.QDialogButtonBox.Ok

        self.buttonBox = QtWidgets.QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(self.accept)

        self.layout = QtWidgets.QVBoxLayout()
        message = QtWidgets.QLabel(
            f"Rip failed for {device}",
        )
        self.layout.addWidget(message)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)


class RipSuccess(QtWidgets.QDialog):

    def __init__(self, device: str, name: str = NAME):
        super().__init__()

        self._name = name
        self.setWindowTitle(f"{self._name}: Rip Success!")

        QBtn = QtWidgets.QDialogButtonBox.Ok

        self.buttonBox = QtWidgets.QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(self.accept)

        self.layout = QtWidgets.QVBoxLayout()
        message = QtWidgets.QLabel(
            f"Rip completed for {device}",
        )
        self.layout.addWidget(message)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)


class SettingsDialog(QtWidgets.QDialog):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        layout = QtWidgets.QVBoxLayout()

        self.widget = SettingsWidget()

        buttons = (
            QtWidgets.QDialogButtonBox.Save
            | QtWidgets.QDialogButtonBox.Cancel
        )
        button_box = QtWidgets.QDialogButtonBox(buttons)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout.addWidget(self.widget)
        layout.addWidget(button_box)

        self.setLayout(layout)

        self.set_settings()

    def set_settings(self):
        self.widget.set_settings()

    def get_settings(self):
        return self.widget.get_settings()


class SettingsWidget(QtWidgets.QWidget):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.dbdir = widgets.PathSelector('Database Location:')
        self.outdir = widgets.PathSelector('Output Location:')

        self.convention_label = QtWidgets.QLabel('Output naming convention')
        self.convention = QtWidgets.QComboBox()
        self.convention.addItems(CONVENTIONS)

        radio_layout = QtWidgets.QVBoxLayout()
        self.features = QtWidgets.QRadioButton("Only Features")
        self.extras = QtWidgets.QRadioButton("Only Extras")
        self.everything = QtWidgets.QRadioButton("All Titles")
        radio_layout.addWidget(
            QtWidgets.QLabel('Titles to Extract')
        )
        radio_layout.addWidget(self.features)
        radio_layout.addWidget(self.extras)
        radio_layout.addWidget(self.everything)
        radio_widget = QtWidgets.QWidget()
        radio_widget.setLayout(radio_layout)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.dbdir)
        layout.addWidget(self.outdir)
        layout.addWidget(self.convention_label)
        layout.addWidget(self.convention)
        layout.addWidget(radio_widget)
        self.setLayout(layout)

    def set_settings(self, settings: dict | None = None):

        if settings is None:
            settings = utils.load_settings()

        self.features.setChecked(True)
        if 'dbdir' in settings:
            self.dbdir.setText(settings['dbdir'])
        if 'outdir' in settings:
            self.outdir.setText(settings['outdir'])
        if 'everything' in settings:
            self.everything.setChecked(settings['everything'])
        if 'extras' in settings:
            self.extras.setChecked(settings['extras'])
        if 'convention' in settings:
            idx = self.convention.findText(settings['convention'])
            if idx != -1:
                self.convention.setCurrentIndex(idx)

    def get_settings(self, save: bool = True):

        settings = {
            'dbdir': self.dbdir.getText(),
            'outdir': self.outdir.getText(),
            'extras': self.extras.isChecked(),
            'everything': self.everything.isChecked(),
            'convention': self.convention.currentText(),
        }
        if save:
            utils.save_settings(settings)

        return settings


class MyQDialog(QtWidgets.QDialog):
    """
    Overload done() and new signal

    Create a new FINISHED signal that will pass bot the result code and
    the dev device. This signal is emitted in the overloaded done() method.

    """

    # The dev device and the result code
    FINISHED = QtCore.pyqtSignal(str, int)

    def done(self, arg):

        super().done(arg)
        self.FINISHED.emit(self.dev, self.result())
