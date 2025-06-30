import logging
import sys
import os
import argparse

from PyQt5 import QtWidgets
from PyQt5 import QtCore
from PyQt5 import QtGui

from .. import LOG, STREAM, ROTFILE, NAME, APP_ICON, TRAY_ICON
from . import metadata
from . import progress
from . import dialogs
from . import utils

if sys.platform.startswith('linux'):
    from ..watchdogs import linux as disc_watchdog
elif sys.platform.startswith('win'):
    from ..watchdogs import windows as disc_watchdog
else:
    raise Exception(f"Platform '{sys.platform}' not currently supported!")


class SystemTray(QtWidgets.QSystemTrayIcon):
    """
    System tray class

    """

    def __init__(self, app, name=NAME):

        super().__init__(QtGui.QIcon(TRAY_ICON), app)

        self.setToolTip(NAME)
        self.__log = logging.getLogger(__name__)
        self._name = name
        self._settingsInfo = None
        self._app = app
        self._menu = QtWidgets.QMenu()

        self.metadata = None

        self._label = QtWidgets.QAction(self._name)
        self._label.setEnabled(False)
        self._menu.addAction(self._label)

        self._menu.addSeparator()

        self._settings = QtWidgets.QAction('Settings')
        self._settings.triggered.connect(self.settings_widget)
        self._menu.addAction(self._settings)

        self._metadata = QtWidgets.QAction('Metadata Editor')
        self._metadata.triggered.connect(self.metadata_widget)
        self._menu.addAction(self._metadata)

        self._menu.addSeparator()

        self._quit = QtWidgets.QAction('Quit')
        self._quit.triggered.connect(self.quit)
        self._menu.addAction(self._quit)

        self.setContextMenu(self._menu)
        self.setVisible(True)

        settings = utils.load_settings()

        self.progress = progress.ProgressDialog()
        self.watchdog = disc_watchdog.Watchdog(
            self.progress,
            **settings,
        )
        self.watchdog.start()

        # Set up check of output directory exists to run right after event
        # loop starts
        QtCore.QTimer.singleShot(
            0,
            self.check_dirs_exists,
        )

    def settings_widget(self, *args, **kwargs):

        self.__log.debug('opening settings')
        settings_widget = dialogs.SettingsDialog()
        if settings_widget.exec_():
            self.watchdog.set_settings(
                **settings_widget.get_settings(),
            )

    def metadata_widget(self, *args, **kwargs):
        """
        Open metadata or bring to focus

        If the metadata attribute is not None, then try to pull focus of
        dialog. Otherwise, we open a new dialog

        """

        if self.metadata is not None:
            self.metadata.setFocus()
            return

        self.metadata = metadata.DiscMetadataEditor(
            '',
            '',
            self.watchdog.dbdir,
        )
        self.metadata.finished.connect(self.metadata_close)

    def metadata_close(self, *args, **kwargs):
        """Run when metadata dialog close for cleanup"""

        self.metadata.deleteLater()
        self.metadata = None

    def quit(self, *args, **kwargs):
        """Display quit confirm dialog"""
        self.__log.info('Quitting program')

        utils.save_settings(
            self.watchdog.get_settings(),
        )

        if kwargs.get('force', False):
            self.__log.info('Force quit')
            self.watchdog.quit()
            self.watchdog.wait()
            self._app.quit()

        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Warning)
        msg.setText("Are you sure you want to quit?")
        msg.setWindowTitle(f"{self._name} Quit")
        msg.setStandardButtons(
            QtWidgets.QMessageBox.Yes
            | QtWidgets.QMessageBox.No
        )
        res = msg.exec_()
        if res == QtWidgets.QMessageBox.Yes:
            self.watchdog.quit()
            self.watchdog.wait()
            self._app.quit()

    def check_dirs_exists(self):
        """
        Check that video output directory exists

        """

        dirs = {
            'outdir': 'Output',
            'dbdir': 'Database',
        }
        for dir, lname in dirs.items():
            val = getattr(self.watchdog, dir)
            if os.path.isdir(val):
                continue

            dlg = dialogs.MissingDirDialog(val, lname)
            if not dlg.exec_():
                self.quit(force=True)
                continue

            path = QtWidgets.QFileDialog.getExistingDirectory(
                QtWidgets.QDialog(),
                f'{self._name}: Select {lname} Folder',
            )
            if path != '':
                setattr(self.watchdog, dir, path)
                settings = self.watchdog.get_settings()
                print(settings)
                utils.save_settings(settings)
                continue

            self.check_dirs_exists()


def cli():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--loglevel',
        type=int,
        default=30,
        help='Set logging level',
    )

    args = parser.parse_args()

    ROTFILE.setLevel(args.loglevel)
    STREAM.setLevel(args.loglevel)
    LOG.addHandler(STREAM)

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName(NAME)
    app.setWindowIcon(QtGui.QIcon(APP_ICON))
    app.setQuitOnLastWindowClosed(False)
    _ = SystemTray(app)
    res = app.exec_()
    sys.exit(res)
