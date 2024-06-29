import logging
import sys
import os
import argparse

from PyQt5.QtWidgets import (
    QApplication,
    QSystemTrayIcon,
    QFileDialog,
    QDialog,
    QMessageBox,
    QMenu,
    QAction,
    QStyle,
)
from PyQt5.QtCore import QTimer

from .. import LOG, STREAM, NAME
from ..ripper import RipperWatchdog

from .progress import ProgressDialog
from .widgets import (
    MissingOutdirDialog,
    SettingsWidget,
)

from .utils import load_settings, save_settings


class SystemTray(QSystemTrayIcon):
    """
    System tray class

    """

    def __init__(self, app, name=NAME):
        icon = (
            QApplication
            .style()
            .standardIcon(
                QStyle.SP_DriveDVDIcon
            )
        )
        super().__init__(icon, app)

        self.__log = logging.getLogger(__name__)
        self._name = name
        self._settingsInfo = None
        self._app = app
        self._menu = QMenu()

        self._label = QAction(self._name)
        self._label.setEnabled(False)
        self._menu.addAction(self._label)

        self._menu.addSeparator()

        self._settings = QAction('Settings')
        self._settings.triggered.connect(self.settings_widget)
        self._menu.addAction(self._settings)

        self._menu.addSeparator()

        self._quit = QAction('Quit')
        self._quit.triggered.connect(self.quit)
        self._menu.addAction(self._quit)

        self.setContextMenu(self._menu)
        self.setVisible(True)

        settings = load_settings()

        self.progress = ProgressDialog()
        self.ripper = RipperWatchdog(
            progress_dialog=self.progress,
            **settings,
        )
        self.ripper.start()

        # Set up check of output directory exists to run right after event
        # loop starts
        QTimer.singleShot(
            0,
            self.check_outdir_exists,
        )

    def settings_widget(self, *args, **kwargs):

        self.__log.debug('opening settings')
        settings_widget = SettingsWidget()
        if settings_widget.exec_():
            self.ripper.set_settings(
                **settings_widget.get_settings(),
            )

    def quit(self, *args, **kwargs):
        """Display quit confirm dialog"""
        self.__log.info('Saving settings')

        save_settings(
            self.ripper.get_settings(),
        )

        if kwargs.get('force', False):
            self.__log.info('Force quit')
            self.ripper.quit()
            self._app.quit()

        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setText("Are you sure you want to quit?")
        msg.setWindowTitle(f"{self._name} Quit")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        res = msg.exec_()
        if res == QMessageBox.Yes:
            self.ripper.quit()
            self._app.quit()

    def check_outdir_exists(self):
        """
        Check that video output directory exists

        """

        if os.path.isdir(self.ripper.outdir):
            return

        dlg = MissingOutdirDialog(self.ripper.outdir)
        if not dlg.exec_():
            self.quit(force=True)
            return

        path = QFileDialog.getExistingDirectory(
            QDialog(),
            f'{self._name}: Select Output Folder',
        )
        if path != '':
            self.ripper.outdir = path
            save_settings(
                self.ripper.get_settings(),
            )
            return

        self.check_outdir_exists()


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

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    _ = SystemTray(app)
    app.exec_()
