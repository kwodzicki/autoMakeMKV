import os

from . import UUID_ROOT, HOMEDIR


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

    for item in os.listdir(root):
        path = os.path.join(root, item)
        src = os.readlink(path)
        src = os.path.abspath(os.path.join(root, src))
        if src == discDev:
            return item

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
