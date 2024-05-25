import logging
import os
import argparse

from .. import STREAM
from .utils import getDiscID, loadData
from .gui import main


def getTitleInfo(discDev, root, dbdir=None):

    log = logging.getLogger(__name__)
    uuid = getDiscID(discDev, root)
    if uuid is None: return

    log.info("UUID of disc: %s", uuid)

    info = loadData(discID=uuid)
    if len(info) == 0:
        info = main(discDev, dbdir=dbdir)

    return info


def cli():
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true', help='Set to enable debugging mode')
    parser.add_argument('--loglevel', type=int, default=30, help='Set logging level')

    args = parser.parse_args()
    STREAM.setLevel( args.loglevel )
    x = main( debug=args.debug )
