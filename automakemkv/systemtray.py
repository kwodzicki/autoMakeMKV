from PyQt5.QtWidgets import (
    QApplication,
    QSystemTrayIcon,
    QMessageBox,
    QMenu,
    QAction,
    QStyle,
)

from PyQt5.QtGui import QIcon




class SystemTray( QSystemTrayIcon ):

    def __init__(self, app):
        icon = (
            QApplication
            .style()
            .standardIcon(
                QStyle.SP_DriveDVDIcon
            )
        )
        super().__init__(icon, app)

        self.setVisible(True) 

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

    def settings(self, *args, **kwargs):

        print( 'opening settings' )

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

if __name__ == "__main__":
    import sys
    app = QApplication( sys.argv )
    app.setQuitOnLastWindowClosed(False)
    w   = SystemTray( app )
    app.exec_()

