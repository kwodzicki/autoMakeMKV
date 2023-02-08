import os

from .utils import getDiscID, loadData
from .gui import main

def getTitleInfo( discDev, root ):

    uuid = getDiscID( discDev, root )
    if uuid is None: return

    info = loadData( discID=uuid )
    if len(info) == 0:
        info = main( discDev )

    return info
