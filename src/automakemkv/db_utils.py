import logging
import os
import re
import gzip
import json

MEDIATYPE = {
    '3840x2160': '4K Blu-Ray (UHD)',
    '1920x1080': 'Blu-Ray',
    '720x480': 'DVD',
}

DISCMETAKEYS = [
    'title',
    'year',
    'tmdb',
    'tvdb',
    'imdb',
    'upc',
    'isMovie',
    'isSeries',
]


def add_disc_info_to_titles(db_root):
    """
    Copy the disc metadata information to
    all tracks that do not have such metadata

    """

    for file in os.listdir(db_root):
        if not file.endswith('.json'):
            continue
        file = os.path.join(db_root, file)

        with open(file, 'r') as iid:
            data = json.load(iid)

        for info in data['titles'].values():
            for key in DISCMETAKEYS:
                if key in info:
                    continue
                info[key] = data.get(key, '')

        with open(file, 'w') as oid:
            json.dump(data, oid, indent=4)


def add_media_type(db_root):
    """
    Add the media_type attribute to database items
    that do not have it.

    Use the resolution of the video to determine what
    the source media was.

    """

    log = logging.getLogger(__name__)
    for file in os.listdir(db_root):
        if not file.endswith('.json'):
            continue
        file = os.path.join(db_root, file)
        info_file = os.path.join(
            db_root,
            os.path.splitext(file)[0]+'.info.gz'
        )
        if not os.path.isfile(info_file):
            log.warning('Could NOT find %s, skipping', info_file)
            continue

        with open(file, 'r') as iid:
            json_data = json.load(iid)

        if 'media_type' in json_data:
            log.info('Media_type already exists: %s', file)
            continue

        try:
            media_type = get_media_type(info_file)
        except Exception as error:
            log.error(error)
            continue

        log.info('Updating data in: %s', file)
        json_data['media_type'] = media_type
        with open(file, 'w') as oid:
            json.dump(json_data, oid, indent=4)


def get_media_type(file: str):

    res = get_vid_res(file)
    if len(res) != 1:
        raise Exception(f'More than one video resolution in file : {file}')

    media_type = MEDIATYPE.get(res[0], None)
    if media_type is None:
        raise Exception(f"No media type matches resolution : {res[0]}")

    return media_type


def get_vid_res(file: str):

    with gzip.open(file) as iid:
        data = iid.read()
    res = set(
        re.findall(rb'(\d{1,}x\d{1,})', data)
    )
    return [val.decode() for val in res]
