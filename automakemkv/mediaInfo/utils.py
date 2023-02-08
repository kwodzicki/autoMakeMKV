import os, json

from PyQt5.QtWidgets import QMessageBox

from .. import DBDIR, UUID_ROOT

EXT = '.json'

def checkInfo( parent, info ):

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

    if message is None:
        return True

    box = QMessageBox(parent)
    box.setText( message )
    box.exec_()
    return False

def getDiscID( discDev, root=UUID_ROOT, **kwargs ):

    for item in os.listdir( root ):
        path = os.path.join( root, item )
        src  = os.readlink( path )
        src  = os.path.abspath( os.path.join(root, src) )
        if src == discDev:
            return item
    return None

def infoPath( discDev, **kwargs ):

    uuid = getDiscID( discDev, **kwargs )
    if uuid is None:
        return None
    return os.path.join( DBDIR, f"{uuid}.info" )

def loadData( discID=None, fpath=None ):

    if fpath is None:
        fpath = os.path.join( DBDIR, f"{discID}{EXT}" )
    if not os.path.isfile( fpath ):
        return {} 

    with open(fpath, 'r') as fid:
        return json.load(fid)

def saveData( info, discDev=None, discID=None, fpath=None, replace=False ):
    """
    Arguments:
        discID (str) : Unique disc ID
        info (dict) : Information from GUI about what
            tracks/titles to rip

    """

    if fpath is None:
        if discDev is not None:
            discID = getDiscID( discDev )
        fpath = os.path.join( DBDIR, f"{discID}{EXT}" )

    if os.path.isfile( fpath ) and not replace:
        return False

    info['discID'] = discID
    with open(fpath, 'w') as fid:
        json.dump(info, fid, indent=4)

    return True

