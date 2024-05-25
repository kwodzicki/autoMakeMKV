import logging
import os

from .utils import getDiscID, loadData
from .gui import main

def getTitleInfo( discDev, root ):

    log = logging.getLogger(__name__)
    uuid = getDiscID( discDev, root )
    if uuid is None: return

    log.info("UUID of disc: %s", uuid)

    info = loadData( discID=uuid )
    if len(info) == 0:
        info = main( discDev )

    return info
