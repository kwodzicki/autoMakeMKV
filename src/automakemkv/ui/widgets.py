import logging
import os

from PyQt5 import QtWidgets


class PathSelector(QtWidgets.QWidget):

    def __init__(self, label, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.log = logging.getLogger(__name__)
        self.path = None

        self.path_text = QtWidgets.QLineEdit()
        self.path_button = QtWidgets.QPushButton('Select Path')
        self.path_button.clicked.connect(self.path_select)

        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self.path_text)
        layout.addWidget(self.path_button)
        widget = QtWidgets.QWidget()
        widget.setLayout(layout)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(QtWidgets.QLabel(label))
        layout.addWidget(widget)

        self.setLayout(layout)

    def connectChanged(self, func):

        self.path_text.textChanged.connect(func)

    def setText(self, var: str) -> None:

        self.path_text.setText(var)

    def getText(self) -> str:

        return self.path_text.text()

    def path_select(self, *args, **kwargs):

        path = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            'Select Folder',
        )
        if path != '' and os.path.isdir(path):
            self.setText(path)
            self.log.info(path)

    def setToolTip(self, txt: str) -> None:
        """
        Set ToolTip for objects

        Sets the ToolTip for the line edit widget and the button to the
        input string

        Arguments:
            txt (str): Text for ToolTip

        """

        self.path_text.setToolTip(txt)
        self.path_button.setToolTip(txt)
