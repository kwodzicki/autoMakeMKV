import logging
import os
import shutil
import re
import json
import gzip

from .. import OUTDIR, DBDIR, SETTINGS_FILE

EXT = '.json'
INFO_EXT = '.info.gz'

TRACKSIZE_AP = 11  # Number used for track size in TINFO from MakeMKV
TRACKSIZE_REG = re.compile(
    rf"TINFO:(\d+),{TRACKSIZE_AP},\d+,\"(\d+)\"",
)


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
    discid: str | None = None,
    hashid: str | None = None,
    fpath: str | None = None,
    dbdir: str | None = None,
) -> tuple:
    """
    Load data from given disc or file

    """

    log = logging.getLogger(__name__)
    dbdir = dbdir or DBDIR

    if fpath is None:
        fpath = db_migrate(discid, hashid, dbdir)

    log.debug("Path to database file : %s", fpath)
    if not os.path.isfile(fpath):
        return None, None

    with open(fpath, 'r') as fid:
        info = json.load(fid)

    infopath = os.path.splitext(fpath)[0] + INFO_EXT
    with gzip.open(infopath, 'rt') as fid:
        data = fid.read()

    sizes = {
        matchobj.group(1): int(matchobj.group(2))
        for matchobj in TRACKSIZE_REG.finditer(data)
    }
    return info, sizes


def db_migrate(discid: str | None, hashid: str, dbdir: str | None):

    log = logging.getLogger(__name__)
    if discid is None:
        log.debug("No 'discid', using new hash")
        return file_from_id(hashid, dbdir)

    old_path = file_from_id(discid, dbdir)
    new_path = file_from_id(hashid, dbdir)

    if not os.path.isfile(old_path):
        log.debug("No old metadata to migrate, using new hash")
        return new_path

    if os.path.isfile(new_path):
        log.debug("New hash exists, using it")
        return new_path

    log.debug("Migrating data: %s --> %s", old_path, new_path)
    old_infopath = os.path.splitext(old_path)[0] + INFO_EXT
    new_infopath = os.path.splitext(new_path)[0] + INFO_EXT
    shutil.copy(old_path, new_path)
    shutil.copy(old_infopath, new_infopath)

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
