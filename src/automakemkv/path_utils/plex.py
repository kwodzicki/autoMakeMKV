"""
Utilities for building file names/paths

When ripping titles, output files must match
naming convention of video_utils package
ingest. These functions ensure that the
file names match what are expected by that
program suite.

"""

import os

EXTRA_LOOKUP = {
    'behindthescenes': 'Behind The Scenes',
    'deleted': 'Deleted Scenes',
    'featurette': 'Featurettes',
    'interview': 'Interviews',
    'scene': 'Scenes',
    'short': 'Shorts',
    'trailer': 'Trailers',
    'other': 'Other',
}


def movie(
    outdir: str,
    info: dict,
    ext: str,
    everything: bool,
    extras: bool,
    movie_lib_name: str | None = None,
    **kwargs,
) -> tuple:
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

    movie_lib_name = movie_lib_name or 'Movies'
    base = '{title} ({year}) {{tmdb-{tmdb}}}'.format(**info)
    fpath = os.path.join(
        outdir,
        movie_lib_name,
        base,
    )

    if info.get('extraTitle', '') != '':
        if info.get('extra', '') != 'edition' and not (everything or extras):
            return None

        if info.get('extra', '') in EXTRA_LOOKUP:
            return os.path.join(
                fpath,
                EXTRA_LOOKUP[info['extra']],
                "{extraTitle}{ext}".format(ext=ext, **info),
            )

        base = "{base} {edition-{{extraTitle}}}".format(base=base, **info)
    elif extras and not everything:
        return None

    return os.path.join(fpath, f"{base}{ext}")


def series(
    outdir: str,
    info: dict,
    ext: str,
    everything: bool,
    extras: bool,
    series_lib_name: str | None = None,
    **kwargs,
) -> tuple:
    """
    Plex format for Series file name

    Build a Plex-formatted file name for a Series
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

    series_lib_name = series_lib_name or 'TV Shows'
    fpath = os.path.join(
        outdir,
        series_lib_name,
        '{title} ({year}) {{tvdb-{tvdb}}}'.format(**info)
    )

    info = info.copy()
    for key in ('season', 'episode'):
        if info.get(key, '') != '':
            info[key] = int(info[key])

    # If a season number is defined, then add "long" season name directory
    # to the fpath
    if info.get('season', '') != '':
        fpath = os.path.join(
            fpath,
            "Season {:02d}".format(int(info['season'])),
        )

    if info.get('extra', '') in EXTRA_LOOKUP:
        if not (everything or extras):
            return None

        if info.get('episode', '') == '':
            # If no episode number defined, then insert extras directory name
            # in path.
            return os.path.join(
                fpath,
                EXTRA_LOOKUP[info['extra']],
                "{episodeTitle}{ext}".format(ext=ext, **info),
            )

        # If here, then episode number was defined and need to append the
        # extra 'type' to the end of the file name
        return os.path.join(
            fpath,
            "{episodeTitle}-{extra}{ext}".format(ext=ext, **info),
        )
    elif extras and not everything:
        return None

    base = (
        '{title} ({year})',
        's{season:02d}e{episode:02d}',
        '{episodeTitle}{ext}',
    )
    return os.path.join(
        fpath,
        ' - '.join(base).format(ext=ext, **info),
    )
