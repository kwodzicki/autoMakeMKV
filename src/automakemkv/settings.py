import logging
import os
import sys
import json
import subprocess
from threading import Lock

from PyQt5 import QtWidgets
from PyQt5 import QtCore

if sys.platform.startswith('win'):
    import ctypes

MOUNT_TYPES = ("nfs", "nfs4", "cifs", "smbfs", "sshfs", "webdav", "afp")


class Settings(QtCore.QObject):
    """
    Manage user settings

    """

    REMOTE_DIALOG = QtCore.pyqtSignal()

    def __init__(
        self,
        settings_file: str,
        videodir: str,
        dbdir: str,
        name: str,
    ):
        """
        Arguments:
            videodir (str): Default output directory

        """
        super().__init__()

        self._log = logging.getLogger(__name__)
        self._lock = Lock()
        self._settings = {}

        self._name = name
        self._settings_file = settings_file
        self._backupdir = os.path.join(videodir, f"{name}_tmp")
        self._is_remote = False

        os.makedirs(self._backupdir, exist_ok=True)

        # Use signal/slot os that dialog is in main thread
        self.REMOTE_DIALOG.connect(self._remote_dialog)

        self.dbdir = dbdir
        self.outdir = videodir

    def __repr__(self) -> str:
        return str(self._settings)

    @QtCore.pyqtSlot()
    def _remote_dialog(self):
        # Slot for trigger warning
        RemoteDirDialog(self.outdir, self.tmpdir, self._name).exec_()

    @property
    def is_remote(self) -> bool:
        return self._is_remote

    @is_remote.setter
    def is_remote(self, val: bool):
        self._is_remote = val
        if val:
            self.REMOTE_DIALOG.emit()

    @property
    def dbdir(self) -> str:
        return self._settings['dbdir']

    @dbdir.setter
    def dbdir(self, val: str):
        self._settings['dbdir'] = val

    @property
    def outdir(self) -> str:
        return self._settings['outdir']

    @outdir.setter
    def outdir(self, val: str):
        self._settings['outdir'] = val
        self.is_remote = is_remote_path(val)

    @property
    def tmpdir(self) -> str:
        if self.is_remote:
            return self._backupdir
        return self._settings['outdir']

    @property
    def everything(self) -> str:
        return self._settings.get('everything', False)

    @everything.setter
    def everything(self, val: str):
        self._settings['everything'] = val

    @property
    def extras(self) -> str:
        return self._settings.get('extras', False)

    @extras.setter
    def extras(self, val: str):
        self._settings['extras'] = val

    @property
    def convention(self) -> str:
        return self._settings.get('convention', 'plex')

    @convention.setter
    def convention(self, val: str):
        self._settings['convention'] = val

    def load(self) -> dict:
        """
        Load dict from data JSON file

        Returns:
            dict: Settings data loaded from JSON file

        """

        with self._lock:
            if os.path.isfile(self._settings_file):
                logging.getLogger(__name__).debug(
                    'Loading settings from %s', self._settings_file,
                )
                with open(self._settings_file, 'r') as fid:
                    self.update(json.load(fid), no_save=True)

                return

        self.save()

    def update(
        self,
        settings: dict | None = None,
        no_save: bool = False,
        **settings_kwargs,
    ) -> None:
        """
        Keyword arguments will override settings dict

        """

        settings = settings or {}
        settings.update(settings_kwargs)
        self._log.debug("Updating settings: %s", settings)
        for key, val in settings.items():
            setattr(self, key, val)

        if not no_save:
            self.save()

    def save(
        self,
        settings: dict | None = None,
    ) -> None:
        """
        Save dict to JSON file

        Arguments:
            settings (dict): Settings to save to JSON file

        """

        with self._lock:
            settings = settings or self._settings

            logging.getLogger(__name__).debug(
                'Saving settings to %s', self._settings_file,
            )
            with open(self._settings_file, 'w') as fid:
                json.dump(settings, fid)


class RemoteDirDialog(QtWidgets.QDialog):
    """
    Dialog to warn about remote directory

    """

    def __init__(self, outdir: str, tmpdir: str, name: str):
        super().__init__()

        self._name = name
        self.setWindowTitle(f"{self._name}: Output Path is Remote Directory")

        QBtn = QtWidgets.QDialogButtonBox.Ok

        self.buttonBox = QtWidgets.QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(self.accept)

        self.layout = QtWidgets.QVBoxLayout()
        message = (
            "The request output directory: ",
            os.linesep,
            outdir,
            os.linesep,
            "looks to be a remote file system.",
            os.linesep,
            "Full disc backups for Blu-rays will be saved to: ",
            os.linesep,
            tmpdir,
            os.linesep,
            "Final output files will still be saved to the requested path.",
            "",
        )
        message = QtWidgets.QLabel(
            os.linesep.join(message)
        )
        self.layout.addWidget(message)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)


def is_remote_path(path: str) -> bool:
    """
    Determine if the given path is located on a remote filesystem

    This function detects remote filesystems on Windows, Linux, and macOS
    using platform-specific methods and filesystem type checks.

    Args:
        path (str): The path to check.

    Returns:
        bool: True if the path is on a remote share, False if it's on a local
            filesystem.

    """

    system = sys.platform
    if system.startswith("win"):
        return is_remote_path_windows(path)
    if system.startswith("linux"):
        return is_remote_path_linux(path)
    if system.startswith("darwin"):
        return is_remote_path_macos(path)
    raise NotImplementedError(f"Unsupported platform: {system}")


def is_remote_path_windows(path):
    """
    Check if a given path on Windows is on a remote network share.

    This uses the Windows API function GetDriveTypeW via ctypes to determine
    if the drive type is DRIVE_REMOTE.

    Args:
        path (str): The path to check.

    Returns:
        bool: True if the path is on a remote share, False otherwise.
    """

    DRIVE_REMOTE = 4

    path = os.path.abspath(path)
    if not path.endswith("\\"):
        path = os.path.splitdrive(path)[0] + "\\"

    GetDriveTypeW = ctypes.windll.kernel32.GetDriveTypeW
    GetDriveTypeW.argtypes = [ctypes.c_wchar_p]
    GetDriveTypeW.restype = ctypes.c_uint

    drive_type = GetDriveTypeW(path)
    return drive_type == DRIVE_REMOTE


def is_remote_path_linux(path: str) -> bool:
    """
    Check if a given path on Linux is mounted from a remote filesystem.

    This attempts detection via /proc/mounts, /etc/mtab, and known GVFS paths,
    and checks for remote fs types like cifs, nfs, smbfs, sshfs, etc.

    Args:
        path (str): The path to check.

    Returns:
        bool: True if the path is on a remote share, False otherwise.
    """

    # 1. Check /proc/mounts
    if check_mounts_file("/proc/mounts", path):
        return True

    # 2. Check /etc/mtab
    if check_mounts_file("/etc/mtab", path):
        return True

    # 3. Check if under GVFS mount
    uid = os.getuid()
    gvfs_path = f"/run/user/{uid}/gvfs"
    try:
        real_path = os.path.realpath(path)
        if real_path.startswith(gvfs_path):
            return True
    except Exception:
        pass

    return False


def check_mounts_file(mounts_file: str, path: str) -> bool:
    """
    Check given mount file for path

    Arguments:
        mounts_file (str): Path to mounts file to check for path
        path (str): Mount point of file system to check is remote

    Returns:
        bool: True if remote, False if local or failed to find

    """

    try:
        with open(mounts_file, "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 3:
                    continue
                mount_point = parts[1]
                fs_type = parts[2]
                if path.startswith(mount_point) and fs_type in MOUNT_TYPES:
                    return True
    except Exception:
        pass
    return False


def is_remote_path_macos(path: str) -> bool:
    """
    Check if a given path on macOS is mounted from a remote filesystem.

    This uses the `mount` command and parses its output to identify remote
    filesystem types (e.g., smbfs, nfs, afp, webdav).

    Args:
        path (str): The path to check.

    Returns:
        bool: True if the path is on a remote share, False otherwise.

    """

    try:
        path = os.path.abspath(path)
        output = subprocess.check_output(["mount"], text=True)
        for line in output.splitlines():
            if "on " in line and "type " in line:
                parts = line.split()
                mount_point = parts[2]
                fs_type = parts[4]
                if path.startswith(mount_point) and fs_type in MOUNT_TYPES:
                    return True
        return False
    except Exception:
        return False
