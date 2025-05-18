import logging
import sys
import os
import argparse

from PyQt5 import QtWidgets
from PyQt5 import QtCore

from .. import LOG, STREAM, NAME
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
        icon = (
            QtWidgets
            .QApplication
            .style()
            .standardIcon(
                QtWidgets.QStyle.SP_DriveDVDIcon
            )
        )
        super().__init__(icon, app)

        self.__log = logging.getLogger(__name__)
        self._name = name
        self._settingsInfo = None
        self._app = app
        self._menu = QtWidgets.QMenu()

        self._label = QtWidgets.QAction(self._name)
        self._label.setEnabled(False)
        self._menu.addAction(self._label)

        self._menu.addSeparator()

        self._settings = QtWidgets.QAction('Settings')
        self._settings.triggered.connect(self.settings_widget)
        self._menu.addAction(self._settings)

        self._menu.addSeparator()

        self._quit = QtWidgets.QAction('Quit')
        self._quit.triggered.connect(self.quit)
        self._menu.addAction(self._quit)

        self.setContextMenu(self._menu)
        self.setVisible(True)

        settings = utils.load_settings()

        self.progress = progress.ProgressDialog()
        self.ripper = disc_watchdog.Watchdog(
            self.progress,
            **settings,
        )
        self.ripper.start()

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
            self.ripper.set_settings(
                **settings_widget.get_settings(),
            )

    def quit(self, *args, **kwargs):
        """Display quit confirm dialog"""
        self.__log.info('Saving settings')

        utils.save_settings(
            self.ripper.get_settings(),
        )

        if kwargs.get('force', False):
            self.__log.info('Force quit')
            self.ripper.quit()
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
            self.ripper.quit()
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
            val = getattr(self.ripper, dir)
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
                setattr(self.ripper, dir, path)
                settings = self.ripper.get_settings()
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

    STREAM.setLevel(args.loglevel)
    LOG.addHandler(STREAM)

    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    _ = SystemTray(app)
    app.exec_()
