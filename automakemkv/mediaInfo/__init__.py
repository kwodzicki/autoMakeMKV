import os

from .utils import getDiscID, loadData
from .gui import main

def getTitleInfo( discDev, root, dbdir=None ):

    uuid = getDiscID( discDev, root )
    if uuid is None:
        return

    info = loadData( discID=uuid, dbdir=dbdir )
    if len(info) == 0:
        info = main( discDev, dbdir=dbdir )

    return info
