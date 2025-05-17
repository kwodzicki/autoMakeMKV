"""
Utilities for building file names/paths

When ripping titles, output files must match
naming convention of video_utils package
ingest. These functions ensure that the
file names match what are expected by that
program suite.

"""

import logging

from . import video_utils, plex

CONVENTIONS = [
    'video_utils',
    'plex',
]


def outfile(
    outdir: str,
    info: dict,
    ext: str = '.mkv',
    everything: bool = False,
    extras: bool = False,
    convention: str | None = None,
    **kwargs,
) -> tuple:
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
        convention (str): Set to either 'video_utils' or 'plex' for file naming
            convention.
            If None, then default to 'video_utils'

    Yields:
        tuple : Disc track ID and path to output file to rip

    """

    log = logging.getLogger(__name__)

    convention = convention or 'video_utils'
    if convention == 'video_utils':
        movie = video_utils.movie
        series = video_utils.series
    elif convention == 'plex':
        movie = plex.movie
        series = plex.series
    else:
        raise ValueError(
            "The 'convention' keyword can be one of 'video_utils' or 'plex'"
        )

    log.debug('Using file convention: %s', convention)

    if not ext.startswith('.'):
        ext = "."+ext

    for tid, title in info.get('titles', {}).items():

        if title['isMovie']:
            func = movie
        elif title['isSeries']:
            func = series

        outfile = func(outdir, title, ext, everything, extras, **kwargs)
        if outfile is None:
            continue

        yield tid, outfile
