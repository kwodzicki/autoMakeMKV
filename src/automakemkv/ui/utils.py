import logging
import os
import sys
import re
import json

if sys.platform.startswith('win'):
    import wmi
    import pythoncom

from .. import DBDIR

EXT = '.json'

TRACKSIZE_AP = 11  # Number used for track size in TINFO from MakeMKV
TRACKSIZE_REG = re.compile(
    rf"TINFO:(\d+),{TRACKSIZE_AP},\d+,\"(\d+)\"",
)


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
