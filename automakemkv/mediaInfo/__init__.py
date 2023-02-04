import os

from .utils import loadData, saveData
from .gui import main

def getTitleInfo( discDev, root ):

    uuid = None
    for item in os.listdir( root ):
        path = os.path.join( root, item )
        src  = os.readlink( path )
        src  = os.path.abspath( os.path.join(root, src) )
        if src == discDev:
            uuid = item
            break

    if uuid is None: return

    info = loadData( uuid )
    if info is None:
        info = main( discDev )
        saveData( uuid, info )

    return info
