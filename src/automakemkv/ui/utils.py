import logging
import os
import sys
import shutil
import re
import json
import subprocess

if sys.platform.startswith('win'):
    import wmi
    import pythoncom
    import ctypes

from .. import OUTDIR, DBDIR, SETTINGS_FILE

EXT = '.json'
INFO_EXT = '.info.gz'

TRACKSIZE_AP = 11  # Number used for track size in TINFO from MakeMKV
TRACKSIZE_REG = re.compile(
    rf"TINFO:(\d+),{TRACKSIZE_AP},\d+,\"(\d+)\"",
)

MOUNT_TYPES = ("nfs", "nfs4", "cifs", "smbfs", "sshfs", "webdav", "afp")


def load_settings() -> dict:
    """
    Load dict from data JSON file

    Returns:
        dict: Settings data loaded from JSON file

    """

    if not os.path.isfile(SETTINGS_FILE):
        settings = {
            'dbdir': DBDIR,
            'outdir': OUTDIR,
            'tmpdir': OUTDIR,
            'everything': False,
            'extras': False,
            'show_status': True,
            'convention': 'plex',
        }
        save_settings(settings)
        return settings

    logging.getLogger(__name__).debug(
        'Loading settings from %s', SETTINGS_FILE,
    )
    with open(SETTINGS_FILE, 'r') as fid:
        return json.load(fid)


def save_settings(settings: dict) -> None:
    """
    Save dict to JSON file

    Arguments:
        settings (dict): Settings to save to JSON file

    """

    logging.getLogger(__name__).debug(
        'Saving settings to %s', SETTINGS_FILE,
    )
    with open(SETTINGS_FILE, 'w') as fid:
        json.dump(settings, fid)


def load_metadata(
    dev: str,
    discid: str | None = None,
    hashid: str | None = None,
    fpath: str | None = None,
    dbdir: str | None = None,
) -> dict:
    """
    Load data from given disc or file

    """

    log = logging.getLogger(__name__)
    dbdir = dbdir or DBDIR

    if fpath is None:
        fpath = db_migrate(dev, discid, hashid, dbdir)

    log.debug("%s - Path to database file : %s", dev, fpath)
    if os.path.isfile(fpath):
        with open(fpath, 'r') as fid:
            return json.load(fid)


def db_migrate(
    dev: str,
    discid: str | None,
    hashid: str,
    dbdir: str | None,
) -> str:

    log = logging.getLogger(__name__)
    if discid is None:
        log.debug("%s - No 'discid', using new hash", dev)
        return file_from_id(hashid, dbdir)

    old_path = file_from_id(discid, dbdir)
    new_path = file_from_id(hashid, dbdir)

    if not os.path.isfile(old_path):
        log.debug("%s - No old metadata to migrate, using new hash", dev)
        return new_path

    if os.path.isfile(new_path):
        log.debug("%s - New hash exists, using it", dev)
        return new_path

    log.debug("%s - Migrating data: %s --> %s", dev, old_path, new_path)
    old_infopath = os.path.splitext(old_path)[0] + INFO_EXT
    new_infopath = os.path.splitext(new_path)[0] + INFO_EXT
    shutil.copy(old_infopath, new_infopath)

    # Read in old json file
    with open(old_path, mode='r') as iid:
        data = json.load(iid)

    # Insert new hash into json
    data['thediscdb'] = hashid

    # Write out data to new file
    with open(new_path, mode='w') as oid:
        json.dump(data, oid, indent=4)

    return new_path


def save_metadata(
    info: dict,
    hashid: str,
    fpath: str | None = None,
    replace: bool = False,
    dbdir: str | None = None,
) -> bool:
    """
    Save disc metadata to JSON file

    Arguments:
        info (dict) : Information from GUI about what tracks/titles to rip

    Keyword argumnets:
        hashid (str) : Unique disc ID

    """

    dbdir = dbdir or DBDIR

    if fpath is None:
        fpath = file_from_id(hashid, dbdir)

    if os.path.isfile(fpath) and not replace:
        return False

    info['hashID'] = hashid
    with open(fpath, 'w') as fid:
        json.dump(info, fid, indent=4)

    return True


def file_from_id(discid: str, dbdir: str | None = None):

    return os.path.join(
        dbdir or DBDIR,
        f"{discid}.json",
    )


def get_vendor_model(path: str) -> tuple[str]:

    vendor = model = ''
    if sys.platform.startswith('linux'):
        vendor, model = linux_vendor_model(path)
    elif sys.platform.startswith('win'):
        pythoncom.CoInitialize()
        try:
            vendor, model = windows_vendor_model(path)
        except Exception:
            pass
        finally:
            pythoncom.CoUninitialize()
    return vendor, model


def linux_vendor_model(path: str) -> tuple[str]:
    """
    Get the vendor and model of drive

    """

    path = os.path.join(
        '/sys/class/block/',
        os.path.basename(path),
        'device',
    )

    vendor = os.path.join(path, 'vendor')
    if os.path.isfile(vendor):
        with open(vendor, mode='r') as iid:
            vendor = iid.read()
    else:
        vendor = ''

    model = os.path.join(path, 'model')
    if os.path.isfile(model):
        with open(model, mode='r') as iid:
            model = iid.read()
    else:
        model = ''

    return vendor.strip(), model.strip()


def windows_vendor_model(path: str) -> tuple[str]:

    c = wmi.WMI()
    for cd in c.Win32_CDROMDrive():
        if cd.Drive != path:
            continue
        return cd.Name, ''

    return '', ''


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
