import logging
import os
import json

from PyQt5.QtWidgets import (
    QApplication,
    QSystemTrayIcon,
    QFileDialog,
    QWidget,
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QRadioButton,
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
        self._settings.triggered.connect( self.settings_widget )
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

    def settings_widget(self, *args, **kwargs):

        self.__log.debug( 'opening settings' )
        settings_widget = SettingsWidget()
        if settings_widget.exec_():
            self.ripper.set_settings(
                **settings_widget.get_settings(),
            )
        
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

class SettingsWidget( QDialog ):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.dbdir      = PathSelector('Database Location:')
        self.outdir     = PathSelector('Output Location:')

        radio_layout    = QVBoxLayout()
        self.features   = QRadioButton("Only Features")
        self.extras     = QRadioButton("Only Extras")
        self.everything = QRadioButton("All Titles")
        radio_layout.addWidget(self.features)
        radio_layout.addWidget(self.extras)
        radio_layout.addWidget(self.everything)
        radio_widget    = QWidget()
        radio_widget.setLayout(radio_layout)

        self.set_settings()

        buttons    = QDialogButtonBox.Save | QDialogButtonBox.Cancel
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
            'dbdir'      : self.dbdir.getText(),
            'outdir'     : self.outdir.getText(),
            'extras'     : self.extras.isChecked(),
            'everything' : self.everything.isChecked(),
        }
        save_settings(settings)
        return settings

class PathSelector(QWidget):

    def __init__(self, label, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.__log       = logging.getLogger(__name__)
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

    def setText(self, var):

        self.path_text.setText(var)

    def getText(self):

        return self.path_text.text()

    def path_select(self, *args, **kwargs):

        path = QFileDialog.getExistingDirectory(self, 'Select Folder')
        if path != '' and os.path.isdir(path):
            self.setText(path)
            self.__log.info(path)

def load_settings():

    if not os.path.isfile(SETTINGS_FILE):
        settings = {
            'dbdir'      : DBDIR,
            'outdir'     : os.path.join(HOMEDIR,'Videos'),
            'everything' : False,
            'extras'     : False,
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

