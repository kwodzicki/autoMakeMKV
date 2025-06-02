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


class MyQDialog(QtWidgets.QDialog):
    """
    Overload done() and new signal

    Create a new FINISHED signal that will pass bot the result code and
    the dev device. This signal is emitted in the overloaded done() method.

    """

    # The dev device and the result code
    FINISHED = QtCore.pyqtSignal(int)

    def __init__(
        self,
        *args,
        timeout: int | float | None = None,
        timeout_code: int | None = None,
        timeout_fmt: str | None = None,
        **kwargs,
    ):
        """
        Keyword arguments:
            timeout (int, float): Amount of time to wait before window auto
                closes. If timeout is set, then both timeout_code and
                timeout_fmt must also be set.
            timeout_code (int): Code to return IF window times out
            timeout_fmt (str): Format string for updating when the window
                will close

        """

        super().__init__(**kwargs)

        self._timer = None
        self._timeout = timeout
        self._timeout_code = timeout_code
        self._timeout_fmt = timeout_fmt

        if (
            self.timeout is not None
            and (self.timeout_code is None or self.timeout_fmt is None)
        ):
            raise ValueError(
                "If 'timeout' is set, then MUST set "
                "'timeout_code' and 'timeout_fmt'!!!"
            )

        self.timeout_label = QtWidgets.QLabel()

    @property
    def timeout(self) -> int | float | None:
        return self._timeout

    @property
    def timeout_code(self) -> int | None:
        return self._timeout_code

    @property
    def timeout_fmt(self) -> str | None:
        return self._timeout_fmt

    def start_timer(self):
        self._timer = QtCore.QTimer()
        self._timer.timeout.connect(self._message_timeout)
        self._timer.start(1000)

    def stop_timer(self):
        if self._timer is not None:
            self._timer.stop()

    def _message_timeout(self):
        """
        Run in time to auto close window

        """

        self._timeout -= 1
        if self._timeout > 0:
            self.timeout_label.setText(
                self.timeout_fmt.format(self._timeout)
            )
            return
        self.stop_timer()
        self.done(self.timeout_code)

    def done(self, arg):

        super().done(arg)
        self.FINISHED.emit(self.result())


class RipFailure(MyQDialog):

    def __init__(self, device: str, fname: str, name: str = NAME):
        super().__init__()

        self._name = name
        self.setWindowTitle(f"{self._name}: Rip Failed!")

        QBtn = QtWidgets.QDialogButtonBox.Ok

        self.buttonBox = QtWidgets.QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(self.accept)

        self.layout = QtWidgets.QVBoxLayout()
        message = QtWidgets.QLabel(
            f"Rip failed for {device}\n\n"
            f"Failed to create file:\n{fname}"
        )
        self.layout.addWidget(message)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)


class RipSuccess(MyQDialog):

    def __init__(self, device: str, fname: str, name: str = NAME):
        super().__init__(
            timeout=30,
            timeout_code=0,
            timeout_fmt="Window will automatically close in {:>4d} seconds",
        )

        self._name = name
        self.setWindowTitle(f"{self._name}: Rip Success!")

        QBtn = QtWidgets.QDialogButtonBox.Ok

        self.buttonBox = QtWidgets.QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(self.accept)

        self.layout = QtWidgets.QVBoxLayout()
        message = QtWidgets.QLabel(
            f"Rip success for {device}\n\n"
            f"Created file:\n{fname}"
        )
        self.layout.addWidget(message)
        self.layout.addWidget(self.timeout_label)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)
        self.start_timer()


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
