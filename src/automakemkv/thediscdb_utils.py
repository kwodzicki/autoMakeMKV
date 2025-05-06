import logging

import os
import json
import gzip


def thediscdb_to_automakemkv(
    thediscdb_path: str,
    automakemkv_path: str | None = None,
) -> None:
    """
    Batch convert TheDiscDB to autoMakeMKV

    Returns:
        None.
    """

    log = logging.getLogger(__name__)

    # Generate path to autoMakeMKV database if not input and ensure dir exists
    if automakemkv_path is None:
        automakemkv_path = os.path.join(
            os.path.expanduser('~'),
            '.automakemkvDB',
        )
    if not os.path.isdir(automakemkv_path):
        os.makedirs(automakemkv_path, exist_ok=True)

    # Search for files in The Disc DB and convert each one to autoMakeMKV
    for res in find_match(thediscdb_path):
        if res is None:
            continue
        metadata, release, titles, mkvdump = res
        outbase = os.path.join(
            automakemkv_path,
            titles['ContentHash']
        )
        metafile = f"{outbase}.json"
        dumpfile = f"{outbase}.info.gz"

        log.info(mkvdump)
        log.info(metafile)
        if os.path.isfile(metafile):
            log.warning(
                'Metadata file alread exists "%s"; Skipping!',
                metafile,
            )
            continue

        new_meta = convert_metadata(metadata, release, titles)
        with open(metafile, mode='w') as oid:
            json.dump(new_meta, oid, indent=4)
        with open(mkvdump, mode='rb') as iid:
            with gzip.open(dumpfile, mode='wb') as oid:
                oid.write(iid.read())


def convert_metadata(
    metadata: dict,
    release: dict,
    titles: dict,
) -> dict:
    """
    Convert metadata for a single disc

    Returns:
        dict: Information for the disc in autoMakeMKV format

    """

    media_type = titles.get('Format', '').lower()
    if 'dvd' in media_type:
        media_type = 'DVD'
    elif 'uhd' in media_type:
        media_type = '4K Blu-Ray (UHD)'
    else:
        media_type = 'Blu-Ray'

    # Base disc-level metadata
    new_metadata = {
        'title': metadata.get('Title', ''),
        'year': metadata.get('Year', ''),
        'tmdb': metadata.get('ExternalIds', {}).get('Tmdb', ''),
        'tvdb': metadata.get('ExternalIds', {}).get('Tvdb', ''),
        'imdb': metadata.get('ExternalIds', {}).get('Imdb', ''),
        'isMovie': metadata.get('Type', '') == 'Movie',
        'isSeries': metadata.get('Type', '') == 'Series',
        'media_type': media_type,
        'upc': release.get('Upc', ''),
        'discID': titles.get('ContentHash', ''),
    }

    # Iterate over all titles, converting to autoMakeMKV format
    new_titles = {}
    for title in titles.get('Titles', []):
        new_title = parse_title(new_metadata, title)
        if new_title is None:
            continue
        index = str(title.get('Index', ''))
        new_titles[index] = new_title

    # Inject converted titles info into dict and return
    new_metadata['titles'] = new_titles
    return new_metadata


def parse_title(disc_meta: dict, title: dict) -> dict:
    """
    Parse data from single title on disc

    For a single title on the disc, parse any metadata from the 'Item' tag
    to build out information for a title that should be extracted from the
    disk.

    Arguments:
        disc_meta (dict): Overall metadata for the disc; some of this
            information is copied to each of the titles
        title (dict): Information for a single title from the disc

    Notes:
        See the ImportBuddy docs for more information about "Types"
        https://github.com/TheDiscDb/data/wiki/Summary-File-Format

    Returns:
        dict: Information for the title in autoMakeMKV format

    """

    item = title.get('Item', None)
    if item is None:
        return None

    # Build up base 'converted' metdata for the title
    converted = {
        'title': disc_meta.get('title', ''),
        'year': disc_meta.get('year', ''),
        'tmdb': disc_meta.get('tmdb', ''),
        'tvdb': disc_meta.get('tvdb', ''),
        'imdb': disc_meta.get('imdb', ''),
        'isMovie': disc_meta['isMovie'],
        'isSeries': disc_meta['isSeries'],
        'extra': '',
        'extraTitle': '',
        'Source Title Id': '',
        'Source FileName': '',
        'Segments Map': title.get('SegmentMap', ''),
        'media_type': disc_meta.get('media_type', ''),
        'upc': disc_meta.get('upc', ''),
    }

    # Key that the 'SourceFile goes under differs for DVD and Blu-Rays
    source = title.get('SourceFile', '')
    if converted['media_type'] == 'DVD':
        converted['Source Title Id'] = source
    else:
        converted['Source FileName'] = source

    # UPdate the extra tag based on title type
    ttype = item.get('Type', '')
    if ttype == 'DeletedScene':
        converted['extra'] = 'deleted'
    elif ttype == 'Trailer':
        converted['extra'] = 'trailer'
    elif ttype == 'Extra':
        converted['extra'] = 'other'

    # Extra info specific to series
    if disc_meta['isSeries']:
        converted['season'] = item.get('Season', '')
        converted['episode'] = item.get('Episode', '')
        converted['episodeTitle'] = item.get('Title', '')
        return converted

    # If here, then has to be a movie; update some more data
    if ttype in ('DeletedScene', 'Trailer', 'Extra'):
        converted['extraTitle'] = item.get('Title', '')

    return converted


def find_match(base: str, content_hash: str | None = None) -> tuple | None:
    """
    Find disc metadata files in The Disc DB

    Walk The Disc DB directory to find all discXX.json files, where XX is a
    disc number of a given release. For each file that has a valid
    'ContentHash' key (that  matches the content_hash the user may or may not
    have provided), data from the ../release.json, ../metadata.json, and
    discXX.json files will be returned, as will the path to the MakeMKV data
    dump at discXX.txt

    Arguments:
        base (str): Path to top-level of The Disc DB

    Keyword arguments:
        content_hash (str): Specific MD5 content hash to search for in The
            Disc DB.

            If found, then only that disc's file information will be yielded.

            If not provided, then will loop over all files with a valid
            'ContentHash'.

    Returns:
        generator: Each generated value will be a:
            tuple:
                - Data from the ../metadata.json file
                - Data from the ../release.json file
                - Data from the discXX.json file
                - Path to the discXX.txt file with MakeMKV data dump

    """

    log = logging.getLogger(__name__)

    for root, dirs, items in os.walk(base):
        for item in items:
            if not item.startswith('disc') or not item.endswith('.json'):
                continue
            path = os.path.join(root, item)
            try:
                with open(path, mode='r') as iid:
                    titles = json.load(iid)
            except Exception as err:
                log.error('Error parsing file "%s": %s', path, err)

            ref_hash = titles.get('ContentHash', None)
            if ref_hash is None:
                log.warning(
                    'No "ContentHash" key found in "%s"; skipping',
                    path,
                )
                continue

            if isinstance(content_hash, str) and ref_hash != content_hash:
                continue

            # If here, then found a match
            release = os.path.join(root, 'release.json')
            metadata = os.path.join(
                os.path.dirname(root),
                'metadata.json',
            )
            mkvdump = os.path.splitext(path)[0] + '.txt'

            with open(release, mode='r') as iid:
                release = json.load(iid)
            with open(metadata, mode='r') as iid:
                metadata = json.load(iid)

            yield metadata, release, titles, mkvdump
            if isinstance(content_hash, str):
                return
