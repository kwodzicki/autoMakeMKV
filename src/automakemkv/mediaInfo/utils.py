import logging
import os
import json
import gzip
import re

from PyQt5.QtWidgets import QMessageBox

from .. import DBDIR, UUID_ROOT

EXT = '.json'
TRACKSIZE_AP = 11  # Number used for track size in TINFO from MakeMKV
TRACKSIZE_REG = re.compile(
    f"TINFO:(\d+),{TRACKSIZE_AP},\d+,\"(\d+)\"",
)


def checkInfo(parent, info: dict):
    """
    Check required disc metadata entered

    """

    message = None
    if not info['isMovie'] and not info['isSeries']:
        message = "Must select 'Movie' or 'Series'"
    elif info['isMovie'] and info['tmdb'] == '':
        message = "Must set TMDb ID"
    elif info['isSeries'] and info['tvdb'] == '':
        message = "Must set TVDb ID"
    elif info['title'] == '':
        message = "Must set Movie/Series Title"
    elif info['year'] == '':
        message = "Must set Movie/Series release year"
    elif ('media_type' in info) and (info['media_type'] == ''):
        message = "Must set media type!"

    if message is None:
        return True

    box = QMessageBox(parent)
    box.setText(message)
    box.exec_()
    return False


def getDiscID(discDev: str, root: str = UUID_ROOT, **kwargs) -> str | None:
    """
    Find disc UUID

    Argumnets:
        discDev (str): Full /dev path of disc

    Keyword arguments:
        root (str): Root path the /dev/disc-by-uuid to determine the UUID of
            the discDvev
        kwargs: Others ignored

    Returns:
        str | None

    """

    for item in os.listdir(root):
        path = os.path.join(root, item)
        src = os.readlink(path)
        src = os.path.abspath(os.path.join(root, src))
        if src == discDev:
            return item

    return None


def info_path(discDev: str, dbdir: str | None = None, **kwargs) -> str | None:
    """
    Get path to MakeMKV info file

    Given "/dev" path to a disc, determine the UUID and build the
    path to the [uuid].info.gz file

    """

    uuid = getDiscID(discDev, **kwargs)
    if uuid is None:
        return None

    dbdir = dbdir or DBDIR

    return os.path.join(dbdir, f"{uuid}.info.gz")


def loadData(
    discID: str | None = None,
    fpath: str | None = None,
    dbdir: str | None = None,
) -> tuple:
    """
    Load data from given disc or file

    """

    log = logging.getLogger(__name__)
    if dbdir is None:
        dbdir = DBDIR

    if fpath is None:
        fpath = os.path.join( dbdir, f"{discID}{EXT}" )

    log.debug("Path to database file : %s", fpath)
    if not os.path.isfile( fpath ):
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


def saveData(
    info: dict,
    discDev: str | None = None,
    discID: str | None = None,
    fpath: str | None = None,
    replace: bool = False,
    dbdir: str | None = None,
) -> bool:
    """
    Save disc metadata to JSON file

    Arguments:
        info (dict) : Information from GUI about what tracks/titles to rip

    Keyword argumnets:
        discID (str) : Unique disc ID

    """

    dbdir = dbdir or DBDIR

    if fpath is None:
        if discDev is not None:
            discID = getDiscID(discDev)
        fpath = os.path.join(dbdir, f"{discID}{EXT}")

    if os.path.isfile(fpath) and not replace:
        return False

    info['discID'] = discID
    with open(fpath, 'w') as fid:
        json.dump(info, fid, indent=4)

    return True

