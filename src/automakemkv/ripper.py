"""
Utilities for ripping titles

"""

import logging
import os
import shutil
import subprocess
from PyQt5 import QtCore

from . import MKVMERGE
from . import utils
from . import disc_hash
from . import makemkv
from . import path_utils
from .ui import metadata

SIZE_POLL = 10
PLAYLIST_DIR = ('BDMV', 'PLAYLIST')
PLAYLIST_EXT = '.mpls'
STREAM_DIR = ('BDMV', 'STREAM')
STREAM_EXT = '.m2ts'
MAKEMKV_SETTINGS = utils.load_makemkv_settings()


class DiscHandler(QtCore.QObject):
    """
    Handle new disc event

    """

    FAILURE = QtCore.pyqtSignal(str)
    SUCCESS = QtCore.pyqtSignal(str)

    def __init__(
        self,
        dev: str,
        outdir: str,
        everything: bool,
        extras: bool,
        convention: str,
        dbdir: str,
        root: str,
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
            convention (str) : Output naming convention to use for

        """

        super().__init__()
        self.log = logging.getLogger(__name__)

        mnt = utils.dev_to_mount(dev)

        self.dev = dev
        self.discid = utils.get_discid(dev, root)
        self.hashid = disc_hash.get_hash(mnt)

        self.outdir = outdir
        self.everything = everything
        self.extras = extras
        self.dbdir = dbdir
        self.root = root
        self.convention = convention
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

        if self.ripper is not None:
            return self.ripper.isRunning()
        return False

        # If ripper not yet defined, still going through motions
        # i.e., running
        if self.ripper is None:
            return True

        # Else, return status of the ripper
        return self.ripper.isRunning()

    def terminate(self, dev: str):
        """
        Kill/close all objects

        """

        if dev != self.dev:
            return

        if self.options is not None:
            self.options.close()
            self.options = None
        if self.metadata is not None:
            self.metadata.close()
            self.metadata = None
        if self.ripper is not None:
            self.ripper.terminate(self.dev)
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

        if self.discid is None and self.hashid is None:
            self.log.info("%s - No UUID found or hash for disc, ignoring", dev)
            return

        # Get title informaiton for tracks to rip
        self.log.info("%s - UUID of disc: %s", dev, self.discid)
        self.log.info("%s - Hash of disc: %s", dev, self.hashid)
        info, sizes = metadata.utils.load_metadata(
            discid=self.discid,
            hashid=self.hashid,
            dbdir=self.dbdir,
        )

        # Open dics metadata GUI and register "callback" for when closes
        if info is None:
            self.disc_metadata_dialog(dev, False)
            return

        # Update mounted information and run rip_disc
        self.info = info
        self.sizes = sizes
        self.options = metadata.ExistingDiscOptions(dev, info, self.convention)
        self.options.FINISHED.connect(self.handle_metadata)

    @QtCore.pyqtSlot(str, bool)
    def disc_metadata_dialog(self, dev: str, load_existing: bool = False):

        if dev != self.dev:
            return

        # Open dics metadata GUI and register "callback" for when closes
        self.metadata = metadata.DiscMetadataEditor(
            dev,
            self.hashid,
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
            utils.eject(dev)
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
                self.options.convention,
                self.progress_dialog,
            )
            self.ripper.FAILURE.connect(self.FAILURE.emit)
            self.ripper.SUCCESS.connect(self.SUCCESS.emit)
            self.ripper.start()
            return

        self.log.error("Unrecognized option: %d", result)


class Ripper(QtCore.QThread):

    FAILURE = QtCore.pyqtSignal(str)
    SUCCESS = QtCore.pyqtSignal(str)

    def __init__(
        self,
        dev: str,
        info: dict,
        sizes: dict,
        outdir: str,
        everything: bool,
        extras: bool,
        convention: str,
        progress,
    ):

        super().__init__()
        self.log = logging.getLogger(__name__)

        self._dead = False
        self.mkv_thread = None
        self.mkv_thread_title = None
        self.dev = dev
        self.info = info
        self.sizes = sizes
        self.outdir = outdir
        self.everything = everything
        self.extras = extras
        self.convention = convention
        self.progress = progress

        # To handle windows mount points, use drive split. Will be
        # empty on linux/mac
        drive, tail = os.path.splitdrive(dev)
        if drive == '':
            tmpdir = os.path.basename(dev)
        else:
            tmpdir = drive.rstrip(":") + "_drive"
        self.tmpdir = os.path.join(outdir, tmpdir)

        if self.progress is not None:
            self.progress.CANCEL.connect(self.terminate)

    def rip(self):

        if self.info is None:
            self.log.error("%s - No title information found/entered", self.dev)
            return

        if self.info == 'skiprip':
            self.log.info("%s - Just saving metadata, not ripping", self.dev)
            return

        paths = dict(
            path_utils.outfile(
                self.outdir,
                self.info,
                everything=self.everything,
                extras=self.extras,
                convention=self.convention,
            )
        )

        # Get list of all titles in the info dict
        title_nums = list(self.info['titles'].keys())
        for title in title_nums:
            if title not in paths:
                _ = self.info['titles'].pop(title)

        self.log.debug(
            "%s - Creating temporary directory : '%s'",
            self.dev,
            self.tmpdir,
        )
        os.makedirs(self.tmpdir, exist_ok=True)

        if len(paths) == 1:
            title, output = list(paths.items())[0]
            return self.rip_title(title, output)

        return self.rip_disc(paths)

    def rip_title(self, title: str, output: str):
        """
        Rip a given title from a disc

        Rip a title from the given disc to
        a specific output file.

        Arguments:
            title (str) : Title to rip
            output (str) : Name of the output file

        Returns:
            bool : True if ripped, False otherwise

        """

        self.log.debug('%s - Running rip title', self.dev)

        if self.progress is not None:
            self.progress.MKV_ADD_DISC.emit(self.dev, self.info, False)

        self.log.info("[%s - %s] Ripping track", self.dev, title)
        self.mkv_thread = makemkv.MakeMKVRip(
            'mkv',
            dev=self.dev,
            title=title,
            output=self.tmpdir,
        )
        self.mkv_thread.FAILURE.connect(self.FAILURE.emit)
        self.mkv_thread.SUCCESS.connect(self.SUCCESS.emit)
        self.mkv_thread.start()

        if self.progress is not None:
            self.progress.MKV_CUR_TRACK.emit(self.dev, title)
            self.mkv_thread.started.wait()
            self.progress.MKV_NEW_PROCESS.emit(
                self.dev,
                self.mkv_thread.proc,
                self.mkv_thread.pipe,
            )

        self.mkv_thread.wait()

        files = [
            os.path.join(self.tmpdir, item)
            for item in os.listdir(self.tmpdir)
            if item.endswith('.mkv')
        ]

        if self.mkv_thread.returncode != 0 or self.mkv_thread.failure:
            fdirs = []
            for fname in files:
                fdir = os.path.dirname(fname)
                fdirs.append(fdir)
                os.remove(fname)
            for fdir in set(fdirs):
                try:
                    os.rmdir(fdir)
                except FileNotFoundError:
                    pass
                else:
                    self.log.debug("%s - Removed dir: %s", self.dev, fdir)

            self.log.error(
                "Error ripping track '%s' from '%s'",
                title,
                self.dev,
            )
            return False

        if len(files) == 0:
            self.log.error(
                "%s - Something went wrong, no output file found!",
                self.dev,
            )
            return False

        if len(files) > 1:
            self.log.error("%s - Too many output files: %s", self.dev, files)
            for fname in files:
                os.remove(fname)
            return False

        self.log.info(
            "%s - Renaming file '%s' ---> '%s'",
            self.dev,
            files[0],
            output,
        )
        # Ensure output directory exists
        os.makedirs(
            os.path.dirname(output),
            exist_ok=True,
        )
        # Rename the file
        os.rename(files[0], output)

        return True

    def rip_disc(self, paths: dict):
        """
        Backup disc then extract titles

        Create a decrypted backup of the disc and then extract the requested
        titles. In most cases this will be faster than re-running makemkvcon
        for each title as there can be signifcant time spent scanning the disc
        to determine the layout of titles.

        Arguments:
            paths (dict) : Title and output mapping for the titles to extract
                from the decrypted disc backup

        Returns:
            bool : True if ripped, False otherwise

        """

        self.log.debug('%s - Running rip disc', self.dev)

        if self.progress is not None:
            self.progress.MKV_ADD_DISC.emit(self.dev, self.info, True)

        tmpfile = 'image.iso'
        tmppath = os.path.join(self.tmpdir, tmpfile)
        self.mkv_thread = makemkv.MakeMKVRip(
            'backup',
            dev=self.dev,
            decrypt=True,
            output=tmppath,
        )
        self.mkv_thread.FAILURE.connect(self.FAILURE.emit)
        self.mkv_thread.SUCCESS.connect(self.SUCCESS.emit)
        self.mkv_thread.start()

        if self.progress is not None:
            # Need option for full disc
            # self.progress.MKV_CUR_TRACK.emit(self.dev, title)
            self.mkv_thread.started.wait()
            self.progress.MKV_NEW_PROCESS.emit(
                self.dev,
                self.mkv_thread.proc,
                self.mkv_thread.pipe,
            )
        self.mkv_thread.wait()

        if self.mkv_thread.returncode != 0 or self.mkv_thread.failure:
            self.log.warning("%s - Error backing up disc", self.dev)
            try:
                os.remove(tmppath)
            except IsADirectoryError:
                shutil.rmtree(tmppath)
            except FileNotFoundError:
                pass
            os.rmdir(self.tmpdir)
            self.log.debug("%s - Removed dir: %s", self.dev, self.tmpdir)
            return False

        # Remove the full-disc progress widget, then re-add not-full-disk
        if self.progress is not None:
            self.progress.MKV_REMOVE_DISC.emit(self.dev)
            self.progress.MKV_ADD_DISC.emit(self.dev, self.info, False)

        # Run title extration based on the media_type
        if self.info.get('media_type', '') == 'DVD':
            self.extract_titles_from_dvd_iso(paths, tmppath)
        else:
            self.extract_titles_from_bluray_iso(paths, tmppath)

        return True

        # Attempt to remove the backup (tmp) file
        if os.path.isdir(tmppath):
            try:
                shutil.rmtree(tmppath)
            except Exception as err:
                self.log.warning(
                    "Failed to remove directory '%s': %s",
                    tmppath,
                    err,
                )
        elif os.path.isfile(tmppath):
            try:
                os.remove(tmppath)
            except Exception as err:
                self.log.warning(
                    "Failed to remove file '%s': %s",
                    tmppath,
                    err,
                )

    def extract_titles_from_bluray_iso(self, paths: dict, src: str) -> None:
        """
        Rip titles from Blu-Ray backup directory

        Blu-ray discs are backed up to a directory, not a ISO file. This
        causes some issues when rescanning the data using MakeMKV where titles
        may not be added in the same order as when accessing the disc.

        So, this method iterates over the titles to rip and and use the source
        filename (.m2ts or .mpls) and the mkvmerge command from MKVToolNix to
        'extract' the titles.

        The language settings from MakeMKV are loaded/used in this process so
        only the preferred languages end up in the output MKV file.

        Argumnets:
            paths (dict): Title numbers and output files to rip
            src (str): Source location of the backup directory

        Returns:
            None

        """

        # Try to get preferred language from MakeMKV settings and set
        # lang_opts if found
        lang = MAKEMKV_SETTINGS.get('app_PreferredLanguage', None)
        if lang is not None:
            lang_opts = [
                '--default-language', lang,
                '--audio-tracks', lang,
                '--subtitle-tracks', lang,
            ]

        # Iterate over all titles/output files to rip
        for title, output in paths.items():
            # Set current track on progress if defined
            if self.progress is not None:
                self.progress.MKV_CUR_TRACK.emit(self.dev, title)

            # Try to get the source playlist/stream for the title
            title_src = (
                self
                .info
                .get('titles', {})
                .get(title, {})
                .get('Source FileName', None)
            )
            if title_src is None:
                self.log.error(
                    "%s - Failed to find playlist name for title '%s', "
                    "skipping.",
                    self.dev,
                    title,
                )
                continue

            # Build full path to file based on extension
            if title_src.endswith(PLAYLIST_EXT):
                title_src = os.path.join(src, *PLAYLIST_DIR, title_src)
            elif title_src.endswith(STREAM_EXT):
                title_src = os.path.join(src, *STREAM_DIR, title_src)
            else:
                self.log.warning(
                    "%s - File not currently supported: %s",
                    self.dev,
                    title_src,
                )
                continue

            # Build mkvmerge command to run
            cmd = [MKVMERGE, '-o', output]
            if lang is not None:
                cmd.extend(lang_opts)
            cmd.append(title_src)

            self.log.debug("%s - Running command: %s", self.dev, cmd)
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                universal_newlines=True,
            )
            if self.progress is not None:
                self.progress.MKV_NEW_PROCESS.emit(self.dev, proc, 'stdout')
            proc.wait()

    def extract_titles_from_dvd_iso(self, paths: dict, src: str) -> None:
        """
        Extract titles from DVD backup

        DVD backups create an ISO file, which, unlike Blu-Rary backups, will
        add titles in the exact same order as the disc when using MakeMKV.
        So, this method iterates over the titles to rip, running MakeMKV to
        extract each title.

        Argumnets:
            paths (dict): Title numbers and output files to rip
            src (str): Source location of the backup directory

        Returns:
            None

        """

        for title, output in paths.items():
            # If progress is set, then update current track
            if self.progress is not None:
                self.progress.MKV_CUR_TRACK.emit(self.dev, title)

            # Initialize MakeMKV process to extract title from ISO
            self.mkv_thread_title = makemkv.MakeMKVRip(
                'mkv',
                title=title,
                iso=src,
                output=self.tmpdir,
            )

            # Start thread, wait for it to start, update progress if set, then
            # wait for extraction to finish
            self.mkv_thread_title.start()
            self.mkv_thread_title.started.wait()
            if self.progress is not None:
                self.progress.MKV_NEW_PROCESS.emit(
                    self.dev,
                    self.mkv_thread_title.proc,
                    self.mkv_thread_title.pipe,
                )
            self.mkv_thread_title.wait()

            # If there was an error during extration
            if self.mkv_thread_title.returncode != 0:
                self.log.warning(
                    "%s - Failed to extract title %s from backup %s",
                    self.dev,
                    title,
                    src,
                )
                continue

            # Get base name of the source file and then get all files in the
            # output directory that are NOT then source file
            fname = os.path.basename(src)
            files = [
                os.path.join(self.tmpdir, item)
                for item in os.listdir(self.tmpdir)
                if item != fname
            ]

            # If number of files found is different that one (1)
            if len(files) != 1:
                self.log.error("%s - Too many output files!", self.dev)
                for fname in files:
                    os.remove(fname)
                continue

            # Rename/move the extracted file to where it should be
            self.log.info(
                "%s - Renaming file '%s' ---> '%s'",
                self.dev,
                files[0],
                output,
            )
            # Ensure output directory exists
            os.makedirs(
                os.path.dirname(output),
                exist_ok=True,
            )
            # Rename the file
            os.rename(files[0], output)

    def run(self):
        """
        Method to run in separate thread

        """

        result = self.rip()

        if result:
            try:
                os.rmdir(self.tmpdir)
            except Exception as err:
                self.log.info(
                    "%s - Failed to remove directory: %s",
                    self.dev,
                    err,
                )

        if self.progress is not None:
            self.progress.MKV_REMOVE_DISC.emit(self.dev)
        self.log.info("%s - Ripper thread finished", self.dev)

    @QtCore.pyqtSlot(str)
    def terminate(self, dev):
        if dev != self.dev:
            return

        self._dead = True
        if self.mkv_thread is None:
            return

        self.log.info("%s - Terminating rip", dev)
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
