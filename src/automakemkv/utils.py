import os
import sys
import time

from PyQt5 import QtCore

from . import UUID_ROOT, LABEL_ROOT, HOMEDIR

TIMEOUT = 60.0  # Timeout to wait for disc to mount


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


class DevToMount(QtCore.QThread):

    FINISHED = QtCore.pyqtSignal(str)

    def __init__(
        self,
        dev: str,
        root: str = LABEL_ROOT,
        **kwargs,
    ):
        super().__init__()

        self.dev = dev
        self.root = root

    def run(self):
        mnt = self.get_mount()
        if mnt is None:
            mnt = ''
        self.FINISHED.emit(mnt)

    def get_mount(self) -> str | None:

        if sys.platform.startswith('win'):
            return self.dev

        uname = os.getlogin()
        t0 = time.monotonic()
        t1 = t0 + TIMEOUT

        # While we have not timed out
        while t0 < t1:
            # Iterate over all items in the root dir
            for item in os.listdir(self.root):
                # Get the real path of the item
                path = os.path.realpath(os.path.join(self.root, item))
                if path != self.dev:
                    continue

                # We try 2 different item values; original and escaped
                for i in range(2):
                    if i == 1:  # If second loop, then escape the string
                        item = item.encode().decode('unicode_escape')
                    # Build full path to what should be mount path
                    path = os.path.join('/media', uname, item)
                    try:
                        _ = os.listdir(path)
                    except Exception:
                        pass
                    else:
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
