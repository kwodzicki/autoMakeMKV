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

class SystemTray( QSystemTrayIcon ):
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

    def settings(self, *args, **kwargs):

        print( 'opening settings' )
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
        print(self.path)

if __name__ == "__main__":
    import sys
    app = QApplication( sys.argv )
    app.setQuitOnLastWindowClosed(False)
    w   = SystemTray( app )
    app.exec_()

