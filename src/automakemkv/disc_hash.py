"""
Compute disc has based on contents

"""

import logging
import os
import sys
import hashlib

HOME = os.path.expanduser('~')


def get_hash(root: str | None) -> str | None:

    log = logging.getLogger(__name__)

    if root is None:
        log.error("No mount point input!")
        return

    bluray_dir = os.path.join(root, 'BDMV', 'STREAM')
    dvd_dir = os.path.join(root, 'VIDEO_TS')

    if os.path.isdir(bluray_dir):
        log.debug('%s - is bluray', root)
        path = bluray_dir
        ext = '.m2ts'
    elif os.path.isdir(dvd_dir):
        log.debug('%s - is dvd', root)
        path = dvd_dir
        ext = ''
    else:
        log.error("%s - Could not determine bluray or dvd", root)
        return

    paths = [
        os.path.join(path, item)
        for item in os.listdir(path)
        if item.endswith(ext)
    ]

    content_hash = hashlib.md5()
    for path in sorted(paths):
        finfo = os.stat(path)
        ss = finfo.st_size.to_bytes(8, byteorder=sys.byteorder, signed=True)
        content_hash.update(ss)

    try:
        return content_hash.hexdigest().upper()
    except Exception as err:
        log.exception(
            'Failed to create disc hash for "%s": %s',
            path,
            err,
        )
        return None


if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        'src',
        type=str,
        help='Disc source to scan/hash',
    )

    parser.add_argument(
        'out',
        type=str,
        help='Output file base name',
    )

    parser.add_argument(
        '--outdir',
        type=str,
        help='Output file base name',
        default=HOME,
    )

    args = parser.parse_args()

    base = f"{args.out}_{sys.platform}"
    hash_file = os.path.join(args.outdir, f"{base}.txt")
    pick_file = os.path.join(args.outdir, f"{base}.pik")

    hash_str = get_hash(args.src)
    print(hash_str)
    with open(hash_file, mode='w') as oid:
        oid.write(hash_str)
    # with open(pick_file, mode='wb') as oid:
    #     pickle.dump(info, oid)
