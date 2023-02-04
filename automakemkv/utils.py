import json

from . import DBDIR

def checkInfo( info ):

    if not info['isMovie'] and not info['isTV']:
        return False
    elif info['isMovie'] and info['tmdb'] == '':
        return False
    elif info['isTV'] and info['tvdb'] == '':
        return False
    return True

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

def toJSON( discID, info ):
    """
    Arguments:
        discID (str) : Unique disc ID
        info (dict) : Information from GUI about what
            tracks/titles to rip

    """

    fpath = os.path.join( DBDIR, f"{discID}.json" )
    with open(fpath, 'wb') as oid:
        json.dump(info, oid)

