import logging
from logging.handlers import RotatingFileHandler

import os

UUID_ROOT = "/dev/disk/by-uuid"

HOMEDIR = os.path.expanduser('~')
DBDIR = os.path.join(
    HOMEDIR,
    f".{__name__}DB",
)
APPDIR = os.path.join(
    HOMEDIR,
    'Library',
    'Application Support',
    __name__,
)
LOGDIR = os.path.join(
    APPDIR,
    'logs',
)

os.makedirs(APPDIR, exist_ok=True)
os.makedirs(LOGDIR, exist_ok=True)

TEST_DATA_FILE = os.path.join(
    APPDIR,
    'testing.txt',
)
SETTINGS_FILE = os.path.join(
    APPDIR,
    'settings.json',
)

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)

STREAM = logging.StreamHandler()
STREAM.setLevel(logging.WARNING)
STREAM.setFormatter(
    logging.Formatter(
        '%(asctime)s [%(levelname).4s] %(message)s'
    )
)

ROTFILE = RotatingFileHandler(
    os.path.join(LOGDIR, f"{__name__}.log"),
    maxBytes=500*2**10,
    backupCount=5,
)
ROTFILE.setLevel(logging.INFO)
ROTFILE.setFormatter(
    logging.Formatter(
        '%(asctime)s [%(levelname).4s] {%(name)s.%(funcName)s} %(message)s'
    )
)

LOG.addHandler(STREAM)
LOG.addHandler(ROTFILE)
