"""
Utilities for building file names/paths

When ripping titles, output files must match
naming convention of video_utils package
ingest. These functions ensure that the
file names match what are expected by that
program suite.

"""

import logging
import os
import re

# Characters that are not allowed in file paths
BADCHARS = re.compile( r'[#%\\\<\>\*\?/\$\!\:\@]' )

def format_dbkey( info ):
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

    keys = ('tmdb', 'tvdb' 'imdb',)
    for key in keys:
        if info[key] == '':
            continue
        key = f"{key}-{info[key]}"
        return f"{{{key}}}"
    return None

def build_series( outdir, info, ext, extras ):
    """
    Plex format for TV Show file name

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



def build_movie( outdir, info, ext, extras ):
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

        fpath.append( format_dbkey( info ) )

        yield tid, os.path.join( outdir, '.'.join(fpath)+ext )

def build_outfile( outdir, info, ext='.mkv', extras=False ):
    """
    Example function for naming output files

    """

    if not os.path.isdir( outdir ):
        os.makedirs( outdir )

    if not ext.startswith('.'):
        ext = "."+ext
    if info['isMovie']:
        func = build_movie
    elif info['isSeries']:
        func = build_series

    yield from func( outdir, info, ext, extras )

def video_utils_dbkey( info ):
    """
    Create database key

    Generate a database key that matches the
    convention for the video_utils package.

    Arguments:
        info (dict) : Contains information about all titles on
            dics that could/should be ripped

    Returns:
        str : Database key

    """
 
    if info['isMovie']:
        keys = ['tmdb', 'imdb']
    elif info['isSeries']:
        keys = ['tvdb', 'imdb']

    for key in keys:
        if info[key] == '':
            continue
        return f"{key}{info[key]}"

    raise Exception('Failed to get database ID')

def video_utils_movie( outdir, info, ext, everything, extras, **kwargs ):
    """
    Generate video_utils compliant movie name

    Will create filenames for movies that are compatiable
    with the input file naming convention for the video_utils
    MakeMKV_Watchdog.

    Arguments:
        outdir (str) : Output directory for ripped title/track
        info (dict) : Contains information about all titles on
            dics that could/should be ripped
        ext (str) : File extension
        everything (bool) : If set, then all titles (i.e., feature and
            all extras) are ripped.
        extras (bool) : If set, then only extras are ripped

    Keyword arguments:
        **kwargs :

    Returns:
        generator : Will return tuple of track ID for MakeMKV and 
            full-path of output file

    """

    log = logging.getLogger(__name__)

    for tid, title in info['titles'].items():
        fpath = [ video_utils_dbkey(title), '' ]
        # If extraTitle is NOT empty, then title is an extra
        if title['extraTitle'] != '':
            # If is NOT 'edition' and neither all nor extras is set, then we aren't ripping title
            if title['extra'] != 'edition' and not (everything or extras):
                continue
            extra = [title['extra'], replace_chars(title['extraTitle'])]
            if extra[0] != 'edition':
                extra = extra[::-1]
            fpath[-1] = '-'.join(extra)
        elif extras:
            continue

        log.info(
            "Will rip: %s (%s) %s-%s",
            title.get('title', ''),
            title.get('year', 'XXXX'),
            title.get('extra', 'extra'),
            title.get('extraTitle', '') or 'NA',
        )
        yield tid, os.path.join( outdir, '.'.join(fpath)+ext )

def video_utils_series( outdir, info, ext, *args, **kwargs ):
    """
    Function for series output naming

    Used to generate path to ripped titles with a
    naming convention that matches that of the
    video_utils python package.

    Arguments:
        outdir (str) : File output directory
        info (dict) : Information about all tracks on disc
            that are flagged for ripping.
        ext (str) : File extension to use
        *args : Any number of other arguments, silently
            ignored

    Keyword arguments:
        **kwargs : Silently ignored

    Yields:
        tuple : Disc track ID and path to output file 

    """

    log = logging.getLogger(__name__)

    for tid, title in info['titles'].items():
        if title['extra'] != '':
            continue

        season  = int(title['season'] )
        season  = f"S{season:02d}"
        episode = list(map(int, title['episode'].split('-')))
        if len(episode) == 1:
            episode = f"E{episode[0]:02d}"
        elif len(episode) > 1:
            episode = f"E{min(episode):02d}-{max(episode):02d}"
        else:
            raise Exception("Issue with epsiode numbering")

        fpath   = [ video_utils_dbkey( title ), season+episode ]
        log.info(
            "Will rip: %s (%s) S%sE%s %s-%s",
            title.get('title', ''),
            title.get('year', 'XXXX'),
            title.get('season', 'XX').zfill(2),
            title.get('episode', 'XX').zfill(2),
            title.get('extra', 'extra'),
            title.get('extraTitle', '') or 'NA',
        )
 
        yield tid, os.path.join( outdir, '.'.join(fpath)+ext )

def video_utils_outfile( outdir, info, ext='.mkv', everything=False, extras=False ):
    """
    General output file namer

    Create output file names that meet the naming
    criteria for the video_utils package. This 
    function will determine if should use movie naming
    or series naming based on inforamtion in the info
    dict.

    Arguments:
        outdir (str) : File output directory
        info (dict) : Information about all tracks on disc
            that are flagged for ripping.
        ext (str) : File extension to use

    Keyword arguments:
        everything (bool) : If set, rip both the main feature(s)/
            episodes AND the extra features. Default is to just
            rip the main feature(s)/episodes
        extras (bool) : If set, rip ONLY the extra features.

    Yields:
        tuple : Disc track ID and path to output file
            to rip 

    """

    if not os.path.isdir( outdir ):
        os.makedirs( outdir )

    if not ext.startswith('.'):
        ext = "."+ext
    if info['isMovie']:
        func = video_utils_movie
    elif info['isSeries']:
        func = video_utils_series

    yield from func( outdir, info, ext, everything, extras )

def _replace( string, repl, **kwargs ):
    """                                                                           
    'Private' function for replace characters in string                           
    
    Arguments:                                                                    
        string (str): String to have characters replaced                            
        repl (str): String to replace bad characters with                           
    
    Keyword arguments:                                                            
        **kwargs: Any, none used currently                                          
    
    Returns:                                                                      
        str: String with bad values repaced by repl value                           
    
    """

    return BADCHARS.sub( repl, string ).replace('&', 'and').strip()

def replace_chars( *args, repl = ' ', **kwargs ):
    """                                                                           
    Replace invalid path characters; '&' replaced with 'and'                      
    
    Arguments:                                                                    
        *args (str): String(s) to replace characters in                             
    
    Keyword arguments:                                                            
        repl (str): String to replace bad characters with; default is space (' ')   
        **kwargs                                                                    
    
    Returns:                                                                      
        String, or list, with bad values replaced by repl value                     
    
    """

    # If one input argument
    if len(args) == 1:
        return _replace( args[0], repl, **kwargs )

    # Iterate over all input arguments, returning list
    return [ _replace( arg, repl, **kwargs ) for arg in args ]

def logger_thread(q):
    """
    To handle logs from other processes

    Arguments:
        q (Queue) : A multiprocessing Queue object that will contain
            log objects from other processes.

    """

    while True:
        record = q.get()
        if record is None:
            break
        logger = logging.getLogger(record.name)
        logger.handle(record)


def get_vendor_model(path):
    """
    Get the vendor and model of drive

    """

    path = os.path.join(
        '/sys/class/block/',
        os.path.basename(path),
        'device',
    )

    vendor = os.path.join(path, 'vendor')
    if os.path.isfile(vendor):
        with open(vendor, mode='r') as iid:
            vendor = iid.read()
    else:
        vendor = ''

    model = os.path.join(path, 'model')
    if os.path.isfile(model):
        with open(model, mode='r') as iid:
            model = iid.read()
    else:
        model = ''

    return vendor.strip(), model.strip()
