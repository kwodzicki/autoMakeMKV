import logging
import os
import re
import json
import gzip

from .. import OUTDIR, DBDIR, SETTINGS_FILE

EXT = '.json'
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
    fpath: str | None = None,
    dbdir: str | None = None,
) -> tuple:
    """
    Load data from given disc or file

    """

    log = logging.getLogger(__name__)
    dbdir = dbdir or DBDIR

    if fpath is None:
        fpath = file_from_discid(discid, dbdir)

    log.debug("Path to database file : %s", fpath)
    if not os.path.isfile(fpath):
        return None, None

    with open(fpath, 'r') as fid:
        info = json.load(fid)

    infopath = os.path.splitext(fpath)[0]+'.info.gz'
    with gzip.open(infopath, 'rt') as fid:
        data = fid.read()

    sizes = {
        matchobj.group(1): int(matchobj.group(2))
        for matchobj in TRACKSIZE_REG.finditer(data)
    }
    return info, sizes


def save_metadata(
    info: dict,
    discid: str,
    fpath: str | None = None,
    replace: bool = False,
    dbdir: str | None = None,
) -> bool:
    """
    Save disc metadata to JSON file

    Arguments:
        info (dict) : Information from GUI about what tracks/titles to rip

    Keyword argumnets:
        discid (str) : Unique disc ID

    """

    dbdir = dbdir or DBDIR

    if fpath is None:
        fpath = os.path.join(dbdir, f"{discid}{EXT}")

    if os.path.isfile(fpath) and not replace:
        return False

    info['discID'] = discid
    with open(fpath, 'w') as fid:
        json.dump(info, fid, indent=4)

    return True


def file_from_discid(discid: str, dbdir: str | None = None):

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


def fancy_time(seconds: float) -> str:

    minutes = int(seconds / 60)
    seconds = round(seconds % 60)

    hours = int(minutes / 60)
    minutes = minutes % 60

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
