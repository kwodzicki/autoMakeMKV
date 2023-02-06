import os, json, gzip

from PyQt5.QtWidgets import QMessageBox

from .. import DBDIR

EXT = '.json.gz'
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

def buildFiles( info ):

    files = {}
    if not checkInfo( info ):
        return files

    if info['isMovie']:
        key = 'tmdb'
    elif info['isTV']:
        key = 'tvdb'
    
    vid = info[key]
    if not vid.startswith(key):
        vid = f"{key}{vid}"
    else:
        raise Exception( 'Must enter either TMDb or TVDb' )

    for title in info['titles']:
        files[title[1]] = f"{vid}.{title[0]}.mkv"

    return files

def loadData( discID ):

    fpath = os.path.join( DBDIR, f"{discID}{EXT}" )
    if not os.path.isfile( fpath ):
        return None

    with gzip.open(fpath, 'rt') as fid:
        return json.load(fid)

def saveData( discID, info, replace=False ):
    """
    Arguments:
        discID (str) : Unique disc ID
        info (dict) : Information from GUI about what
            tracks/titles to rip

    """

    fpath = os.path.join( DBDIR, f"{discID}{EXT}" )
    if os.path.isfile( fpath ) and not replace:
        return False

    with gzip.open(fpath, 'wt') as fid:
        json.dump(info, fid, indent=4)

    return True

