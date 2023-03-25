"""
Utilities for building file names/paths

When ripping titles, output files must match
naming convention of video_utils package
ingest. These functions ensure that the
file names match what are expected by that
program suite.

"""

import os

def formatDbKey( info ):
    """
    Plex format for database ID

    Build a Plex-formatted database ID

    Arguments:
        info (dict) : Information from GUI

    Returns:
        str, None : If a database key exists in the
            info dict, then return database id string,
            else return None.

    """

    keys = ['tmdb', 'tvdb' 'imdb']
    for key in keys:
        if info[key] == '': continue
        key = f"{key}-{info[key]}"
        return f"{{{key}}}"
    return None

def buildMovie( outdir, info, ext, extras ):
    """
    Plex format for Movie file name

    Build a Plex-formatted file name for a Movie
    given inforamtion about the title.

    Arguments:
        outdir (str) : Output directoy to place ripped
            file in.
        info (dict) : Information about all titles that
            should be ripped.
        ext (str) : File extension
        extras (bool) : If set, then generate file paths
            for movie 'extras'

    Returns:
        tuple : Yields a tuple of track ID to rip and the
            path to save the ripped file to

    """

    for tid, title in info['titles'].items():
        if title['extra'] == 'edition':
            fpath   = [f"{info['title']} ({info['year']})"]
            edition = title['extraTitle'] 
            if title['extraTitle'] != '':
                edition = "{" + f"edition-{edition}" + "}"
            fpath.append( edition )
        elif extras:
            fpath = [f"{title['extraTitle']}-{title['extra']}", ""]
        else:
            continue

        fpath.append( formatDbKey( info ) )

        yield tid, os.path.join( outdir, '.'.join(fpath)+ext )

def buildOutfile( outdir, info, ext='.mkv', extras=False ):

    if not os.path.isdir( outdir ):
        os.makedirs( outdir )

    if not ext.startswith('.'): ext = "."+ext
    if info['isMovie']:
        func = buildMovie
    elif info['isSeries']:
        func = buildSeries

    yield from func( outdir, info, ext, extras )

def video_utils_dbkey( info ):

    if info['isMovie']:
        keys = ['tmdb', 'imdb']
    elif info['isSeries']:
        keys = ['tvdb', 'imdb']

    for key in keys:
        if info[key] == '': continue
        return f"{key}{info[key]}"
    raise Exception('Failed to get database ID')


def video_utils_movie( outdir, info, ext, *args, **kwargs ):

    for tid, title in info['titles'].items():
        if title['extra'] == 'edition':
            fpath = [ video_utils_dbkey( info ), title['extraTitle'] ] 
        else:
            continue

        yield tid, os.path.join( outdir, '.'.join(fpath)+ext )

def video_utils_series( outdir, info, ext, *args, **kwargs ):

    for tid, title in info['titles'].items():
        if title['extra'] == '':
            season  = int(title['season'] )
            episode = int(title['episode'])
            fpath   = [ video_utils_dbkey( info ), f"S{season:02d}E{episode:02d}" ]
        else:
            continue

        yield tid, os.path.join( outdir, '.'.join(fpath)+ext )

def video_utils_outfile( outdir, info, ext='.mkv', extras=False ):

    if not os.path.isdir( outdir ):
        os.makedirs( outdir )

    if not ext.startswith('.'): ext = "."+ext
    if info['isMovie']:
        func = video_utils_movie 
    elif info['isSeries']:
        func = video_utils_series

    yield from func( outdir, info, ext, extras )
