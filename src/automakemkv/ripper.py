"""
Utilities for ripping titles

"""

import logging
from collections.abc import Callable
import os
import subprocess
from PyQt5 import QtCore

from . import utils
from . import makemkv
from .ui import metadata

SIZE_POLL = 10


class DiscHandler(QtCore.QObject):
    """
    Handle new disc event

    """

    def __init__(
        self,
        dev: str,
        outdir: str,
        everything: bool,
        extras: bool,
        dbdir: str,
        root: str,
        filegen: Callable,
        progress_dialog,
        **kwargs,
    ):
        """
        Arguments:
            dev (str): Dev device
            outdir (str) : Top-level directory for ripping files
            everything (bool) : If set, then all titles identified
                for ripping will be ripped. By default, only the
                main feature will be ripped
            extras (bool) : If set, only 'extra' features will
                be ripped along with the main title(s). Main
                title(s) include Theatrical/Extended/etc.
                versions for movies, and episodes for series.
            root (str) : Location of the 'by-uuid' directory
                where discs are mounted. This is used to
                get the unique ID of the disc.
            filegen (func) : Function to use to generate
                output file names based on information
                from the database. This function must
                accept (outdir, info, extras=bool), where info is
                a dictionary of data loaded from the
                disc database, and extras specifies if
                extras should be ripped.

        """

        super().__init__()
        self.log = logging.getLogger(__name__)

        self.dev = dev
        self.discid = utils.get_discid(dev, root)
        self.outdir = outdir
        self.everything = everything
        self.extras = extras
        self.dbdir = dbdir
        self.root = root
        self.filegen = filegen
        self.progress_dialog = progress_dialog

        self.options = None
        self.metadata = None
        self.ripper = None

        self.info = None
        self.sizes = None

        self.disc_lookup(self.dev)

    def isRunning(self):
        """
        Check if is running

        """

        # If ripper not yet defined, still going through motions
        # i.e., running
        if self.ripper is None:
            return True

        # Else, return status of the ripper
        return self.ripper.isRunning()

    def terminate(self):
        """
        Kill/close all objects

        """

        if self.options is not None:
            self.options.close()
            self.options = None
        if self.metadata is not None:
            self.metadata.close()
            self.metadata = None
        if self.ripper is not None:
            self.ripper.terminate()
            self.ripper = None

    @QtCore.pyqtSlot(str)
    def disc_lookup(self, dev: str):
        """
        Get information about a disc

        Given the /dev path to a disc, load information from database if
        it exists or open GUI for user to input information

        Arguments:
            dev (str) : Device to rip from

        """

        if dev != self.dev:
            return

        if self.discid is None:
            self.log.info("%s - No UUID found for disc, ignoring", dev)
            return

        # Get title informaiton for tracks to rip
        self.log.info("%s - UUID of disc: %s", dev, self.discid)
        info, sizes = metadata.utils.load_metadata(discid=self.discid)

        # Open dics metadata GUI and register "callback" for when closes
        if info is None:
            self.disc_metadata_dialog(dev, False)
            return

        # Update mounted information and run rip_disc
        self.info = info
        self.sizes = sizes
        self.options = metadata.ExistingDiscOptions(dev, info)
        self.options.FINISHED.connect(self.handle_metadata)

    @QtCore.pyqtSlot(str, bool)
    def disc_metadata_dialog(self, dev: str, load_existing: bool = False):

        if dev != self.dev:
            return

        # Open dics metadata GUI and register "callback" for when closes
        self.metadata = metadata.DiscMetadataEditor(
            dev,
            self.discid,
            self.dbdir,
            load_existing=load_existing,
        )
        self.metadata.FINISHED.connect(self.handle_metadata)

    @QtCore.pyqtSlot(str, int)
    def handle_metadata(self, dev: str, result: int):
        """
        Rip a whole disc

        Given information about a disc, rip
        all tracks. Intended to be run as thread
        so watchdog can keep looking for new discs

        Arguments:
            dev (str) : Device to rip from
            root (str) : Location of the 'by-uuid' directory
                where discs are mounted. This is used to
                get the unique ID of the disc.
            outdir (str) : Directory to save mkv files to
            extras (bool) : Flag for if should rip extras

        """

        if dev != self.dev:
            return

        # Check the "return" status of the dialog
        if result == metadata.IGNORE:
            self.log.info("%s - Ignoring disc", dev)
            return

        # Data already saved to disc by the metadata editor
        if result == metadata.SAVE:
            self.log.info("Requested metadata save and eject: %s", dev)
            subprocess.call(['eject', dev])
            return

        if result == metadata.OPEN:
            self.disc_metadata_dialog(dev, True)
            return

        # If metadata attribute is not None, then must be new disc or
        # the user edited/updated something
        if self.metadata is not None:
            self.info = self.metadata.info
            self.sizes = self.metadata.sizes

        # Initialize ripper object
        if result == metadata.RIP:
            self.ripper = Ripper(
                dev,
                self.info,
                self.sizes,
                self.outdir,
                self.everything,
                self.extras,
                self.filegen,
                self.progress_dialog,
            )
            self.ripper.start()
            return

        self.log.error("Unrecognized option: %d", result)


class Ripper(QtCore.QThread):

    def __init__(
        self,
        dev: str,
        info: dict,
        sizes: dict,
        outdir: str,
        everything: bool,
        extras: bool,
        filegen: Callable,
        progress,
    ):

        super().__init__()
        self.log = logging.getLogger(__name__)

        self._dead = False
        self.dev = dev
        self.info = info
        self.sizes = sizes
        self.outdir = outdir
        self.everything = everything
        self.extras = extras
        self.filegen = filegen
        self.progress = progress

        self.progress.CANCEL.connect(self.terminate)

    def rip_disc(self):

        if self.info is None:
            self.log.error("%s - No title information found/entered", self.dev)
            return

        if self.info == 'skiprip':
            self.log.info("%s - Just saving metadata, not ripping", self.dev)
            return

        paths = dict(
            self.filegen(
                self.outdir,
                self.info,
                everything=self.everything,
                extras=self.extras,
            )
        )

        # Get list of all titles in the info dict
        title_nums = list(self.info['titles'].keys())
        for title in title_nums:
            if title not in paths:
                _ = self.info['titles'].pop(title)

        self.log.info('Emitting add disc signal')
        self.progress.ADD_DISC.emit(self.dev, self.info)

        for title, path in paths.items():
            self.rip_title(title, path)
            if self._dead:
                return

    def rip_title(self, title, outfile):
        """
        Rip a given title from a disc

        Rip a title from the given disc to
        a specific output file.

        Arguments:
            title (str) : Title to rip
            outfile (str) : Name of the output file

        Returns:
            bool : True if ripped, False otherwise

        """

        outdir = os.path.dirname(outfile)
        if not os.path.isdir(outdir):
            os.makedirs(outdir)

        tmpdir = os.path.splitext(
            os.path.basename(outfile),
        )[0]
        tmpdir = os.path.join(outdir, tmpdir)
        self.log.debug("Creating temporary directory : '%s'", tmpdir)
        os.makedirs(tmpdir, exist_ok=True)

        if self.progress is not None:
            self.progress.CUR_TRACK.emit(self.dev, title)

        self.log.info("[%s - %s] Ripping track", self.dev, title)
        self.mkv_thread = makemkv.MakeMKVRip(
            self.dev,
            title,
            tmpdir,
            noscan=True,
            minlength=0,
        )
        self.mkv_thread.start()

        # while (
        #     not RUNNING.wait(timeout=SIZE_POLL)
        #     and self.mkv_thread.isRunning()
        # ):

        # while self.mkv_thread.isRunning():
        while not self.mkv_thread.wait(SIZE_POLL*1000):
            cursize = directory_size(tmpdir)
            self.progress.TRACK_SIZE.emit(
                self.dev,
                round(cursize/self.sizes[title]*100),
            )

        # if RUNNING.is_set():
        #     self.mkv_thread.quit()
        #     self.mkv_thread.wait()
        #     return

        if self._dead:
            self.mkv_thread.terminate()
            self.mkv_thread.wait()
            return

        files = [
            os.path.join(tmpdir, item) for item in os.listdir(tmpdir)
        ]

        status = False
        if self.mkv_thread.returncode != 0:
            fdirs = []
            for fname in files:
                fdirs.append(os.path.dirname(fname))
                os.remove(fname)
            for fdir in set(fdirs):
                try:
                    os.rmdir(fdir)
                except FileNotFoundError:
                    pass
            self.log.error(
                "Error ripping track '%s' from '%s'",
                title,
                self.dev,
            )
        elif len(files) != 1:
            self.log.error('Too many output files!')
            for fname in files:
                os.remove(fname)
        else:
            self.log.info("Renaming file '%s' ---> '%s'", files[0], outfile)
            os.rename(files[0], outfile)
            status = True

        try:
            os.rmdir(tmpdir)
        except FileNotFoundError:
            pass

        return status

    def run(self):
        self.rip_disc()
        self.progress.REMOVE_DISC.emit(self.dev)
        subprocess.call(['eject', self.dev])

    @QtCore.pyqtSlot(str)
    def terminate(self, dev):
        if dev != self.dev:
            return

        self._dead = True
        if self.mkv_thread is None:
            return
        self.mkv_thread.terminate()


def directory_size(path):
    """
    Get size of all files in directory

    """

    return sum(
        d.stat().st_size
        for d in os.scandir(path)
        if d.is_file()
    )
