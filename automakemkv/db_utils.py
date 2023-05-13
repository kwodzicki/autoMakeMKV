import os
import re
import gzip
import json

MEDIATYPE = {
    '3840x2160' : '4K Blu-Ray (UHD)',
    '1920x1080' : 'Blu-Ray',
    '720x480'   : 'DVD',
}

def add_media_type( db_root ):

    for file in os.listdir( db_root ):
        if not file.endswith('.json'):
            continue
        info_file = os.path.join(
            db_root,
            os.path.splitext(file)[0]+'.info.gz'
        )
        if not os.path.isfile(info_file):
            print(f'Could NOT find {info_file}, skipping')
            continue

        with open(file, 'r') as iid:
            json_data = json.load( iid )

        if 'media_type' in json_data:
            print( f'Media_type already exists : {file}' )
            continue

        try:
            media_type = get_media_type( info_file )
        except Exception as error:
            print( error )
            continue

        print(f'Updating data in : {file}')
        json_data['media_type'] = media_type
        with open(file, 'w') as oid:
            json.dump(json_data, oid, indent=4)

def get_media_type( file ):

    res = get_vid_res(file)
    if len(res) != 1:
        raise Exception( f'More than one video resolution in file : {file}' )

    media_type = MEDIATYPE.get( res[0], None )
    if media_type is None:
        raise Exception( f"No media type matches resolution : {res[0]}" )

    return media_type

def get_vid_res( file ):

    with gzip.open(file) as iid:
        data = iid.read()
    res = set( re.findall(rb'(\d{1,}x\d{1,})', data ) )
    return [val.decode() for val in res]


