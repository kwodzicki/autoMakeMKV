import logging

import os
import re
import json
import zipfile
import gzip


def thediscdb_to_automakemkv(
    thediscdb_path: str,
    automakemkv_path: str | None = None,
    update: bool = False,
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
        path, metadata, release, titles, mkvdump = res
        outbase = os.path.join(
            automakemkv_path,
            titles['ContentHash']
        )
        metafile = f"{outbase}.json"
        dumpfile = f"{outbase}.info.gz"

        log.info(metafile)
        if os.path.isfile(metafile) and not update:
            log.warning(
                'Metadata file alread exists "%s"; Skipping!',
                metafile,
            )
            continue

        print('Working on:', path)
        new_meta = convert_metadata(metadata, release, titles)
        with open(metafile, mode='w') as oid:
            json.dump(new_meta, oid, indent=4)
        with open(dumpfile, mode='wb') as oid:
            oid.write(mkvdump)


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
        'thediscdb': titles.get('ContentHash', ''),
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
        'extra': 'edition',
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

    item_title = item.get('Title', '')
    mm = re.search(r'\(([^\)]*)\)', item_title)  # Search for edition info
    # If here, then has to be a movie; update some more data
    if ttype in ('DeletedScene', 'Trailer', 'Extra'):
        converted['extraTitle'] = item_title
    elif mm is not None:
        # Title may have extra info in it (edition like Director's Cut).
        # Use regex to search for pattern, but ask user about if is edition
        # info or just part of the name
        print(
            f'The item "{item_title}" may have edition info in the title.'
        )
        print(
            f'Is the information "{mm.group(1)}" info about an edition? '
            " E.g., Director's Cut, Extended Edition, etc."
        )
        resp = input('INFO/REMOVE/ignore: ')

        item_title = item_title.replace(mm.group(0), '').rstrip()
        if resp == 'INFO':
            print("Updating information to specify edition...")
            converted['extraTitle'] = mm.group(1)
            converted['title'] = item_title
        elif resp == 'REMOVE':
            print("Removing information from name...")
            converted['title'] = item_title
        else:
            print(f"You entered '{resp}', assuming part of title.")
        print()

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

    if os.path.isdir(base):
        for root, dirs, items in os.walk(base):
            for item in items:
                yield item_checker(open, root, item, content_hash)
    elif os.path.isfile(base) and base.endswith('.zip'):
        with zipfile.ZipFile(base) as zipid:
            for path in zipid.namelist():
                root, item = os.path.split(path)
                yield item_checker(zipid.open, root, item, content_hash)
    else:
        raise ValueError(f"Could not determine database type: {base}")


def item_checker(
    opener,
    root: str,
    item: str,
    content_hash: str | None = None,
):

    log = logging.getLogger(__name__)
    if not item.startswith('disc') or not item.endswith('.json'):
        return None

    path = os.path.join(root, item)
    try:
        with opener(path, mode='r') as iid:
            titles = json.load(iid)
    except Exception as err:
        log.error('Error parsing file "%s": %s', path, err)
        return None

    ref_hash = titles.get('ContentHash', None)
    if ref_hash is None:
        log.warning(
            'No "ContentHash" key found in "%s"; skipping',
            path,
        )
        return None

    if isinstance(content_hash, str) and ref_hash != content_hash:
        return None

    # If here, then found a match
    release = os.path.join(root, 'release.json')
    metadata = os.path.join(
        os.path.dirname(root),
        'metadata.json',
    )
    mkvdump = os.path.splitext(path)[0] + '.txt'

    with opener(release, mode='r') as iid:
        release = json.load(iid)
    with opener(metadata, mode='r') as iid:
        metadata = json.load(iid)
    with opener(mkvdump, mode='r') as iid:
        mkvdump = gzip.compress(iid.read())

    return path, metadata, release, titles, mkvdump
    if isinstance(content_hash, str):
        return None
