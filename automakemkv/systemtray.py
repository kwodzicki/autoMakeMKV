import logging
import os
import json

from PyQt5.QtWidgets import (
    QApplication,
    QSystemTrayIcon,
    QFileDialog,
    QWidget,
    QMessageBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QMenu,
    QAction,
    QStyle,
    QVBoxLayout,
    QHBoxLayout,
)
from PyQt5.QtGui import QIcon

from . import HOMEDIR, DBDIR, SETTINGS_FILE
from .ripper import RipperWatchdog, RUNNING

class SystemTray(QSystemTrayIcon):
    """
    System tray class

    """

    def __init__(self, app):
        icon = (
            QApplication
            .style()
            .standardIcon(
                QStyle.SP_DriveDVDIcon
            )
        )
        super().__init__(icon, app)

        self.__log = logging.getLogger(__name__)
        self._settingsInfo = None
        self._app  = app
        self._menu = QMenu()

        self._label = QAction( 'autoMakeMKV' )
        self._label.setEnabled(False)
        self._menu.addAction( self._label )

        self._menu.addSeparator()
        self._settings = QAction( 'Settings' )
        self._settings.triggered.connect( self.settings )
        self._menu.addAction( self._settings )
    
        self._menu.addSeparator() 
        self._quit = QAction( 'Quit' )
        self._quit.triggered.connect( self.quit )
        self._menu.addAction( self._quit )

        self.setContextMenu( self._menu )
        self.setVisible(True) 

        settings = load_settings()
        self.ripper = RipperWatchdog(**settings)
        self.ripper.start()

    def settings(self, *args, **kwargs):

        self.__log.debug( 'opening settings' )
        self._settingsInfo = SettingsWidget()

    def quit(self, *args, **kwargs):
        """Display quit confirm dialog"""

        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setText("Are you sure you want to quit?")
        msg.setWindowTitle("autoMakeMKV Quit")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        res = msg.exec_()
        if res == QMessageBox.Yes:
            RUNNING.clear()
            self._app.quit()

class SettingsWidget( QWidget ):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.database = PathSelector('Database Location:')
        self.output   = PathSelector('Output Location:')

        layout = QVBoxLayout()
        layout.addWidget(self.database)
        layout.addWidget(self.output)
        
        self.setLayout(layout)
        self.show()

class PathSelector(QWidget):

    def __init__(self, label, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.path        = None

        self.path_text   = QLineEdit()
        self.path_button = QPushButton('Select Path')
        self.path_button.clicked.connect( self.path_select )

        layout = QHBoxLayout()
        layout.addWidget(self.path_text) 
        layout.addWidget(self.path_button) 
        widget = QWidget()
        widget.setLayout(layout)

        layout = QVBoxLayout()
        layout.addWidget(QLabel(label))
        layout.addWidget(widget)

        self.setLayout(layout)

    def path_select(self, *args, **kwargs):

        self.path = QFileDialog.getExistingDirectory(self, 'Select Folder')
        self.__log.info(self.path)

def load_settings():

    if not os.path.isfile(SETTINGS_FILE):
        settings = {
            'dbdir'  : DBDIR,
            'outdir' : os.path.join(HOMEDIR,'Videos'),
        }
        save_settings(settings)
        return settings

    logging.getLogger(__name__).debug(
        'Loading settings from %s', SETTINGS_FILE,
    )
    with open(SETTINGS_FILE, 'r') as fid:
        return json.load(fid)

def save_settings(settings):

    logging.getLogger(__name__).debug(
        'Saving settings to %s', SETTINGS_FILE,
    )
    with open(SETTINGS_FILE, 'w') as fid:
        json.dump(settings, fid)
     
if __name__ == "__main__":
    import sys
    app = QApplication( sys.argv )
    app.setQuitOnLastWindowClosed(False)
    w   = SystemTray( app )
    app.exec_()

