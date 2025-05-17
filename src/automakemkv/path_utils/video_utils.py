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

from .utils import replace_chars


def movie(
    outdir: str,
    info: dict,
    ext: str,
    everything: bool,
    extras: bool,
    **kwargs,
) -> str | None:
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

    fpath = [dbkey(info), '']
    # If extraTitle is NOT empty, then title is an extra
    if info['extraTitle'] != '':
        # If is NOT 'edition' and neither all nor extras is set,
        # then we aren't ripping title
        if info['extra'] != 'edition' and not (everything or extras):
            return None
        extra = [info['extra'], replace_chars(info['extraTitle'])]
        if extra[0] != 'edition':
            extra = extra[::-1]
        fpath[-1] = '-'.join(extra)
    elif extras and not everything:
        return None

    log.info(
        "Will rip: %s (%s) %s-%s",
        info.get('title', ''),
        info.get('year', 'XXXX'),
        info.get('extra', 'extra'),
        info.get('extraTitle', '') or 'NA',
    )
    return os.path.join(outdir, '.'.join(fpath)+ext)


def series(
    outdir: str,
    info: dict,
    ext: str,
    *args,
    **kwargs,
) -> str | None:
    """
    Function for series output naming

    Used to generate path to ripped titles with a
    naming convention that matches that of the
    video_utils python package.

    Arguments:
        outdir (str) : File output directory
        title_id (str): Title number to rip
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

    if info['extra'] != '':
        return None

    season = int(info['season'])
    season = f"S{season:02d}"
    episode = list(
        map(int, info['episode'].split('-'))
    )
    if len(episode) == 1:
        episode = f"E{episode[0]:02d}"
    elif len(episode) > 1:
        episode = f"E{min(episode):02d}-{max(episode):02d}"
    else:
        raise Exception("Issue with epsiode numbering")

    fpath = [dbkey(info), season+episode]
    log.info(
        "Will rip: %s (%s) S%sE%s %s-%s",
        info.get('title', ''),
        info.get('year', 'XXXX'),
        info.get('season', 'XX').zfill(2),
        info.get('episode', 'XX').zfill(2),
        info.get('extra', 'extra'),
        info.get('extraTitle', '') or 'NA',
    )

    return os.path.join(outdir, '.'.join(fpath)+ext)


def dbkey(info: dict) -> str:
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
