import os
import sys
import time

from . import UUID_ROOT, LABEL_ROOT, HOMEDIR

TIMEOUT = 20.0  # Timeout to wait for disc to mount


def get_discid(discDev: str, root: str = UUID_ROOT, **kwargs) -> str | None:
    """
    Find disc UUID

    Argumnets:
        discDev (str): Full /dev path of disc

    Keyword arguments:
        root (str): Root path the /dev/disc-by-uuid to determine the UUID of
            the discDvev
        kwargs: Others ignored

    Returns:
        str | None

    """

    if not sys.platform.startswith('linux'):
        return

    for item in os.listdir(root):
        path = os.path.join(root, item)
        src = os.readlink(path)
        src = os.path.abspath(os.path.join(root, src))
        if src == discDev:
            return item

    return


def dev_to_mount(dev: str, root: str = LABEL_ROOT, **kwargs) -> str | None:

    # If on windows, dev is already mount point
    if sys.platform.startswith('win'):
        return dev

    uname = os.getlogin()
    t0 = time.monotonic()
    t1 = t0 + TIMEOUT

    while t0 < t1:
        for item in os.listdir(root):
            path = os.path.realpath(os.path.join(root, item))
            if path != dev:
                continue

            path = os.path.join('/media', uname, item)
            try:
                _ = os.listdir(path)
            except Exception:
                break

            return path

        time.sleep(3.0)
        t0 = time.monotonic()

    return None


def load_makemkv_settings() -> dict:
    """
    Load MakeMKV settings file

    """

    settings = {}
    file = os.path.join(HOMEDIR, '.MakeMKV', 'settings.conf')
    if not os.path.isfile(file):
        return settings

    with open(file, mode='r') as iid:
        for line in iid.readlines():
            try:
                key, val = line.strip().split('=')
            except Exception:
                continue
            settings[key.strip()] = val.strip().strip('"')

    return settings