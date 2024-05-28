import logging
import os

from .. import STREAM
from .utils import getDiscID, loadData
from .gui import MainWidget


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
    import sys
    import argparse
    from PyQt5.QtWidgets import QApplication
    parser = argparse.ArgumentParser()
    parser.add_argument('discdev', type=str)
    parser.add_argument('--debug', action='store_true', help='Set to enable debugging mode')
    parser.add_argument('--loglevel', type=int, default=30, help='Set logging level')
   

    args = parser.parse_args()
    STREAM.setLevel( args.loglevel )
    app = QApplication(sys.argv)
    MainWidget(args.discdev)
    app.exec_()
