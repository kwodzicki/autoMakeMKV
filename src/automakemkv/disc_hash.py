"""
Compute disc has based on contents

"""

import logging
import os
import sys
# import pickle
from hashlib import sha256

HOME = os.path.expanduser('~')


def get_hash(root: str | None) -> str | None:

    log = logging.getLogger(__name__)

    if root is None:
        log.error("No mount point input!")
        return

    items = os.listdir(root)

    if 'BDMV' in items:
        log.debug('is bluray')
        return bluray_hash(root)

    if 'VIDEO_TS' in items or 'AUDIO_TS' in items:
        log.debug('is dvd')
        return dvd_hash(root)

    log.warning("Could not determine disc type!")
    return


def dvd_hash(root: str) -> str:
    """
    Generate hash for DVD

    Get tuple of path to each file in VIDEO_TS and AUDIO_TS directories
    along with the size of each file to create hash for disc

    """

    info = []

    for subdir in ('VIDEO_TS', 'AUDIO_TS'):
        subdir = os.path.join(root, subdir)
        if not os.path.isdir(subdir):
            continue

        for item in os.listdir(subdir):
            path = os.path.join(subdir, item)
            if not os.path.isfile(path):
                continue

            fsize = os.stat(path).st_size
            path = os.path.normpath(path).replace(root, '')
            if path.startswith(os.sep):
                path = path[1:]
            path = ''.join(
                path.split(os.sep)
            )
            info.append(
                (path, fsize),
            )
    if len(info) == 0:
        raise Exception("No files found, could not create hash!")

    info = sorted(info, key=lambda x: x[0])

    return (
        sha256(
            str(info).encode()
        )
        .hexdigest()
    )


def bluray_hash(root: str) -> str:
    """
    Generate has from index.bdmv

    There should(?) alwasy be an index.bdmv file in the BDMV directory,
    so just hash the contents of that to get the disc id

    """

    mcmf = os.path.join(root, 'BDMV', 'index.bdmv')
    with open(mcmf, mode='rb') as iid:
        data = iid.read()
    return sha256(data).hexdigest()


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
