"""
Utilities for ripping titles

"""

import logging
import os
import copy
import shutil
import subprocess

from PyQt5 import QtCore

from . import MKVMERGE
from . import utils
from . import disc_hash
from . import makemkv
from . import path_utils
from .ui import metadata
from .ui.dialogs import BackupExists, DiscHashFailure

SIZE_POLL = 10
PLAYLIST_DIR = ('BDMV', 'PLAYLIST')
PLAYLIST_EXT = '.mpls'
STREAM_DIR = ('BDMV', 'STREAM')
STREAM_EXT = '.m2ts'
BACKUP_FILE = 'image.iso'
MAKEMKV_SETTINGS = utils.load_makemkv_settings()


class DiscHandler(QtCore.QObject):
    """
    Handle new disc event

    """

    # String object is path of the output file to be created
    FAILURE = QtCore.pyqtSignal(str)
    SUCCESS = QtCore.pyqtSignal(str)

    FINISHED = QtCore.pyqtSignal()
    EJECT_DISC = QtCore.pyqtSignal()

    DISC_METADATA_DIALOG = QtCore.pyqtSignal(bool)
    EXTRACT_TITLE = QtCore.pyqtSignal(str)

    def __init__(
        self,
        dev: str,
        outdir: str,
        everything: bool,
        extras: bool,
        convention: str,
        dbdir: str,
        root: str,
        progress,
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

        self.DISC_METADATA_DIALOG.connect(self.disc_metadata_dialog)
        self.EXTRACT_TITLE.connect(self.extract_title)

        self._cancelled = False
        self._delay_eject = False  # used during backup then tag

        self.cleanup = True

        self.backup_path = None
        self.mnt = None
        self.paths = {}

        self.dev = dev
        self.outdir = outdir
        self.everything = everything
        self.extras = extras
        self.dbdir = dbdir
        self.root = root
        self.convention = convention
        self.progress = progress
        self.progress.CANCEL.connect(self.cancel)

        self.disc_hasher = None
        self.options = None
        self.metadata = None
        self.ripper = None
        self.extractor = None

        self.info = None

        # To handle windows mount points, use drive split. Will be
        # empty on linux/mac. Append monotonic time to directory to
        # help ensure not collisions
        drive, tail = os.path.splitdrive(dev)
        if drive == '':
            tmpdir = os.path.basename(dev)
        else:
            tmpdir = drive.rstrip(":") + "_drive"
        self._tmpdir = os.path.join(outdir, tmpdir)

        self.hashid = None
        self.discid = utils.get_discid(dev, root)  # This is pretty quick

        # Finding mount point can take a little bit, so we do in thread.
        # On windows, this thread should finish right away
        self.dev_to_mnt = utils.DevToMount(dev)
        self.dev_to_mnt.FINISHED.connect(self.found_mount_point)
        self.dev_to_mnt.start()

    @property
    def hash(self) -> str | None:
        return self.hashid or self.discid

    @property
    def tmpdir(self) -> str:
        if self.hash is None:
            return self._tmpdir
        return f"{self._tmpdir}_{self.hash}"

    def isRunning(self):
        """
        Check if is running

        """

        if self.ripper is not None:
            return self.ripper.isRunning()
        return False

    def use_existing_backup(self, output: str) -> bool:
        """
        Returns:
            bool: If true, then use the existing backup, else create new

        """

        # If output doesn't exist, then return False; i.e., new backup
        if not os.path.exists(output):
            return False

        dlg = BackupExists(output)
        return dlg.exec_()  # Return True if using existing, False otherwise

    @QtCore.pyqtSlot(str)
    def cancel(self, dev: str):
        """
        Kill/close all objects

        This needs to accept a dev variable becasue the signal that
        triggers it comes from the main progress widget, which is not tied
        to a specific dev, but rather tracks a collection of progress
        widgets. These widgets are tracked by the source of the MakeMKV
        command; a disc/dev or a backup file. This is what is passed here
        and used to check that we are trying to cancel the correct object.

        """

        if dev != self.dev and dev != self.backup_path:
            return

        self._cancelled = True
        if self.ripper is not None:
            self.log.debug("%s - Cancelling ripper", dev)
            self.ripper.CANCEL.emit()

        if self.extractor is not None:
            self.log.debug("%s - Cancelling extractor", dev)
            self.extractor.CANCEL.emit()

    @QtCore.pyqtSlot(str)
    def found_mount_point(self, mnt: str) -> None:
        """
        Callback for mount point found

        On windows, the 'dev' device is the mount point, so it takes no time
        to look that up. However, on Linux, everything is done by /dev/
        device and udev events for a disc insert can come before the disc is
        fully mounted to a path. So, there are tries/retries that occur when
        trying to deteremine the mount point from the /dev/ device. This is
        done in a QThread so as to not block GUI operations.

        When the search is finished, the objects FINISHED signal is emitted,
        calling this method to set up a DiscHash lookup.

        Arguments:
            mnt (str): The mount point of the disc. If no mount point
                determined, this will be an empty string

        """

        # Clean up the thread object for mount point lookup
        self.dev_to_mnt.deleteLater()
        self.dev_to_mnt = None

        # We compute disc hash in thread to keep the GUI alive.
        # When finished will trigger the disc_lookup method,
        # passing in the disc hash
        self.mnt = None if mnt == '' else mnt
        self.disc_hasher = disc_hash.DiscHasher(self.mnt)
        self.disc_hasher.FINISHED.connect(self.disc_lookup)
        self.disc_hasher.start()

    @QtCore.pyqtSlot(str)
    def disc_lookup(self, hashid: str):
        """
        Get information about a disc

        Given the /dev path to a disc, load information from database if
        it exists or open GUI for user to input information

        Arguments:
            dev (str) : Device to rip from

        """

        if self.disc_hasher is not None:
            self.disc_hasher.wait()  # Should be quick
            self.disc_hasher.deleteLater()

        # If hash is an emtpy string, then ensure that attribute is None
        self.hashid = hashid if hashid != '' else None

        if self.hashid is None:
            self.log.info(
                "%s - No hash for disc, ignoring",
                self.dev,
            )
            DiscHashFailure(self.dev, self.mnt).exec_()
            return

        # Get title informaiton for tracks to rip
        self.log.info("%s - UUID of disc: %s", self.dev, self.discid)
        self.log.info("%s - Hash of disc: %s", self.dev, self.hashid)
        info = metadata.utils.load_metadata(
            self.dev,
            discid=self.discid,
            hashid=self.hashid,
            dbdir=self.dbdir,
        )

        # Open dics metadata GUI and register "callback" for when closes
        if info is None:
            self.DISC_METADATA_DIALOG.emit(False)
            return

        # Update mounted information and run rip_disc
        self.info = info
        self.existing_disc(metadata.RIP)

    @QtCore.pyqtSlot(int)
    def existing_disc(self, result: int):

        # If metadata attribute is not None, then must be new disc or
        # the user edited/updated something
        if self.metadata is not None:
            self.log.debug("%s - Cleaning up the metadata window", self.dev)
            self.info = self.metadata.info
            self.metadata.deleteLater()
            self.metadata = None

        # Check the "return" status of the dialog
        if result == metadata.IGNORE:
            self.log.info("%s - Ignoring disc", self.dev)
            self.FINISHED.emit()
            return

        # If we are OPENING the disc info for editing
        if result == metadata.OPEN:
            self.DISC_METADATA_DIALOG.emit(True)
            return

        # Data already saved to disc by the metadata editor
        if result == metadata.SAVE:
            self.log.info("%s - Requested metadata save and eject", self.dev)
            self.EJECT_DISC.emit()
            self.FINISHED.emit()
            return

        # If we want to backup, then reopen metadata for tagging
        if result == metadata.BACKUP_THEN_TAG:
            output = os.path.join(self.tmpdir, BACKUP_FILE)
            if self.use_existing_backup(output):
                # If using existing, then call method and then return
                self.rip_finished(output)
                return

            self._delay_eject = True
            self.ripper = RipDisc(
                self.dev,
                self.info,
                output,
                self.progress,
                eject=False,  # Do NOT eject when doing backup then tag
            )
            self.ripper.FAILURE.connect(self.FAILURE.emit)
            self.ripper.SUCCESS.connect(self.SUCCESS.emit)
            self.ripper.EJECT_DISC.connect(self.EJECT_DISC.emit)
            self.ripper.FINISHED.connect(self.backup_then_tag)
            self.ripper.start()
            return

        # Initialize ripper object
        if result != metadata.RIP:
            self.log.error("%s - Unrecognized option: %d", self.dev, result)
            return

        if self.info is None:
            self.log.error("%s - No title information found/entered", self.dev)
            return

        if self.info == 'skiprip':
            self.log.info("%s - Just saving metadata, not ripping", self.dev)
            return

        self.options = metadata.ExistingDiscOptions(
            self.dev,
            self.info,
            self.convention,
            self.extras,
            self.everything,
        )
        self.options.FINISHED.connect(self.handle_metadata)

    @QtCore.pyqtSlot(bool)
    def disc_metadata_dialog(self, load_existing: bool = False):

        # Open dics metadata GUI and register "callback" for when closes
        self.metadata = metadata.DiscMetadataEditor(
            self.dev,
            self.hashid,
            self.dbdir,
            load_existing=load_existing,
        )
        self.metadata.FINISHED.connect(self.existing_disc)

    @QtCore.pyqtSlot(str)
    def backup_then_tag(self, backup_path: str):
        """
        Arguments:
            backup_path (str): Path to the disc backup

        """

        success = self.ripper.result
        self.progress.MKV_REMOVE_DISC.emit(self.dev)
        if not success:
            self.log.warning("Backup failed, not opening metadata window!")
            self.FINISHED.emit()
            return

        self.backup_path = backup_path
        self.metadata = metadata.DiscMetadataEditor(
            self.dev,
            self.hashid,
            self.dbdir,
            load_existing=True,
            backed_up=True,
        )
        self.metadata.FINISHED.connect(self.existing_disc)

    @QtCore.pyqtSlot(int)
    def handle_metadata(self, result: int) -> None:
        """
        Main handler for options and metadata events

        When a disc is inserted, if it is in the database and options window
        is presented asking how to handle the disc. If the disc is not in the
        database, then a dialog for tagging the disc is presented. When either
        of those windows is closed, the method is used as a callback for how
        to handle the user's selection.

        The value passed into this fuction is one of any number of integers
        (set in the metadata.py module) signaling what to do.

        Arguments:
            result (int): Return code from options or metadata dialog for how
                to process the disc

        """

        # Get convention from window; we update the attribute because
        # if they changed it and then opened to edit metadata, the
        # selection would be lost.
        convention = self.options.convention
        checked = self.options.checked
        self.log.debug("%s - Cleaning up the options window", self.dev)
        self.options.deleteLater()
        self.options = None

        # Check the "return" status of the dialog
        if result == metadata.IGNORE:
            self.log.info("%s - Ignoring disc", self.dev)
            self.FINISHED.emit()
            return

        # If we are OPENING the disc info for editing
        if result == metadata.OPEN:
            self.DISC_METADATA_DIALOG.emit(True)
            return

        # Initialize ripper object
        if result != metadata.RIP:
            self.log.error("%s - Unrecognized option: %d", self.dev, result)
            return

        if self.info is None:
            self.log.error("%s - No title information found/entered", self.dev)
            return

        if self.info == 'skiprip':
            self.log.info("%s - Just saving metadata, not ripping", self.dev)
            return

        # I got a little lazy and did not want to rewrite the outfile code.
        # So, if we have checked values, then we filter down the list of
        # titles in a copy of the info dict to only those that have been
        # checked by the user. We also set everything = True and extras = False
        # to ensure that all titles, which have been manually filtered, are
        # ripped.
        info = copy.deepcopy(self.info)
        info['titles'] = {
            key: val
            for i, (key, val) in enumerate(info['titles'].items())
            if checked[i]
        }

        # Get all paths to output files created during rip
        self.paths.update(
            dict(
                path_utils.outfile(
                    self.outdir,
                    info,
                    everything=True,
                    extras=False,
                    convention=convention,
                )
            )
        )

        # Get list of all titles in the info dict
        title_nums = list(self.info['titles'].keys())
        for title in title_nums:
            if title not in self.paths:
                _ = self.info['titles'].pop(title)

        # If backup_path is set, then we did a backup then tag event, so disc
        # is already backed up and we need to extract titles.
        if self.backup_path is not None:
            self.rip_finished(self.backup_path)
            return

        self.log.debug(
            "%s - Creating temporary directory : '%s'",
            self.dev,
            self.tmpdir,
        )
        os.makedirs(self.tmpdir, exist_ok=True)

        # Set up ripper based on single or multi-title rip
        # The FINISHED signal processing is specific to type
        # of rip
        if len(self.paths) == 1:
            title, output = list(self.paths.items())[0]
            self.ripper = RipTitle(
                self.dev,
                title,
                self.info,
                output,
                self.tmpdir,
                self.progress,
            )
        else:
            output = os.path.join(self.tmpdir, BACKUP_FILE)
            if self.use_existing_backup(output):
                # If using existing, then call method and then return
                self.rip_finished(output)
                return

            self.ripper = RipDisc(
                self.dev,
                self.info,
                output,
                self.progress,
            )

        # These signals are the same for both rip types
        self.ripper.FAILURE.connect(self.FAILURE.emit)
        self.ripper.SUCCESS.connect(self.SUCCESS.emit)
        self.ripper.EJECT_DISC.connect(self.EJECT_DISC.emit)
        self.ripper.FINISHED.connect(self.rip_finished)

        # Start the thread
        self.ripper.start()

    @QtCore.pyqtSlot(str)
    def rip_finished(self, backup_path: str) -> None:
        """
        Handle cleanup/title extraction after rip

        If extracting only one title from the disc, then we just clean
        up some objects and emit a FINISHED signal. Otherwise, we need
        to extract titles from the disc backup, and so we set up an
        extractor instance and get that started.

        Arguments:
            backup_path (str): Full path to the backup of the disc to extract
                titles from

        """

        success = True
        if self.ripper is not None:
            self.ripper.wait()  # This "shouldn't" take too long
            success = self.ripper.result

        self.progress.MKV_REMOVE_DISC.emit(self.dev)
        if success:
            # If RipTitle instance, then we are done
            if isinstance(self.ripper, RipTitle):
                self.FINISHED.emit()
            else:
                self.backup_path = backup_path
                self.progress.MKV_ADD_DISC.emit(backup_path, self.info, False)
                self.EXTRACT_TITLE.emit('')

        self.log.debug("%s - Cleaning up the ripper thread", self.dev)

        if self.ripper is not None:
            self.ripper.deleteLater()
            self.ripper = None

        # IF failed, then emit FINISHED for cleanup
        if not success:
            try:
                os.rmdir(self.tmpdir)
            except Exception:
                pass
            self.FINISHED.emit()

        # If eject was delayed, run eject now
        if self._delay_eject:
            self.log.debug('%s - Running delayed eject', self.dev)
            self.EJECT_DISC.emit()

    @QtCore.pyqtSlot(str)
    def extract_title(self, previous_output: str) -> None:
        """
        Handle title extraction from backup

        When extracting multiple titles from a disc, a full backup
        is done to reduce the overhead of multiple set-up scans of
        the disc. So, after backup is done, this method is triggered
        to start extraction of each title in sequence. This is done
        by connecting the FINISHED signal of each extraction object
        back to this method so that after each one finishes, we
        retrigger this method to extract the next one.

        Arguments:
            previous_output (str): Full path of output file from previous
                rip or extraction. This is not used except for callback
                from full disc rip

        """

        # If the extractor is defined, then ensure is stopped and delete
        if self.extractor is not None:
            self.extractor.wait()
            self.extractor.deleteLater()

        # If there are still titles to extract (paths left) AND we have
        # not had a cancel event
        if len(self.paths) > 0 and not self._cancelled:
            # Run title extration based on the media_type
            if self.info.get('media_type', '') == 'DVD':
                self.extractor = ExtractFromDVD(
                    self.backup_path,
                    self.paths,
                    self.tmpdir,
                    self.progress,
                )
            else:
                self.extractor = ExtractFromBluRay(
                    self.backup_path,
                    self.paths,
                    self.info,
                    self.progress
                )

            self.extractor.FAILURE.connect(self.FAILURE.emit)
            self.extractor.SUCCESS.connect(self.SUCCESS.emit)
            self.extractor.FINISHED.connect(self.extract_title)
            self.extractor.start()

            return

        # If made here, then all extractions have finished OR cancelled
        self.extractor = None
        self.progress.MKV_REMOVE_DISC.emit(self.backup_path)

        if self.cleanup:
            # Attempt to remove the backup (tmp) file
            self.log.debug(
                "%s - Removing temporary directory: %s",
                self.dev,
                self.tmpdir,
            )

            if os.path.isdir(self.tmpdir):
                try:
                    shutil.rmtree(self.tmpdir)
                except Exception as err:
                    self.log.warning(
                        "Failed to remove directory '%s': %s",
                        self.tmpdir,
                        err,
                    )
            elif os.path.isfile(self.tmpdir):
                try:
                    os.remove(self.tmpdir)
                except Exception as err:
                    self.log.warning(
                        "Failed to remove file '%s': %s",
                        self.tmpdir,
                        err,
                    )

        # Emit FINISHED to ensure cleanup of the object
        self.FINISHED.emit()


class RipTitle(makemkv.MakeMKVRip):
    """
    Extract a single title from disc

    """

    def __init__(
        self,
        dev: str,
        title: str,
        info: dict,
        fname: str,
        tmpdir: str,
        progress,
    ):
        """
        Rip a given title from a disc

        Rip a title from the given disc to
        a specific output file.

        Arguments:
            title (str) : Title to rip
            output (str) : Name of the output file
            info (dict): Info about tracks on the disc; needed
                for progress window
            fname (str): Output file name for the title

        Returns:
            bool : True if ripped, False otherwise

        """

        super().__init__(
            'mkv',
            dev=dev,
            title=title,
            output=tmpdir,
        )

        self.fname = fname
        self.progress = progress
        self.progress.MKV_ADD_DISC.emit(self.dev, info, False)

    def run(self):
        """Run in thread"""

        try:
            self._result = self.rip()
        except Exception as err:
            self.log.exception(
                "%s - Failed to rip title: %s",
                self.source[1],
                err,
            )
        self.FINISHED.emit(self.fname)

    def rip(self):

        self.log.info("[%s - %s] Ripping rip title", self.dev, self.title)
        self.makemkvcon()  # Start process for rip/extract

        # Set up a progress widget
        self.progress.MKV_CUR_TRACK.emit(self.dev, self.title)
        self.progress.MKV_NEW_PROCESS.emit(
            self.dev,
            self.proc,
            self.pipe,
        )

        # Wait for process to finish
        self.monitor_proc()

        # Eject the disc
        self.EJECT_DISC.emit()

        # Get listing of files in output directory
        files = [
            os.path.join(self.output, item)
            for item in os.listdir(self.output)
            if item.endswith('.mkv')
        ]

        # If bad return code or failure
        if self.returncode != 0 or self.failure:
            self.FAILURE.emit(self.fname)
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
                self.title,
                self.dev,
            )
            return False

        if len(files) == 0:
            self.FAILURE.emit(self.fname)
            self.log.error(
                "%s - Something went wrong, no output file found!",
                self.dev,
            )
            return False

        if len(files) > 1:
            self.FAILURE.emit(self.fname)
            self.log.error("%s - Too many output files: %s", self.dev, files)
            for fname in files:
                os.remove(fname)
            return False

        self.SUCCESS.emit(self.fname)
        self.log.info(
            "%s - Renaming file '%s' ---> '%s'",
            self.dev,
            files[0],
            self.fname,
        )
        # Ensure output directory exists
        os.makedirs(
            os.path.dirname(self.fname),
            exist_ok=True,
        )
        # Rename the file
        os.rename(files[0], self.fname)

        return True


class RipDisc(makemkv.MakeMKVRip):
    """
    Full disc backup

    """

    def __init__(
        self,
        dev: str,
        info: dict,
        output: str,
        progress,
        eject: bool = True,
    ):
        """
        Rip a given title from a disc

        Rip a title from the given disc to
        a specific output file.

        Arguments:
            dev (str) : Path of disc to backup
            info (dict): Inforamtion about disc
            tmpdir (str): Directory to backup to
            progress (str): Main progress widget

        """

        super().__init__(
            'backup',
            dev=dev,
            decrypt=True,
            output=output,
        )

        self._eject = eject
        self.progress = progress
        self.progress.MKV_ADD_DISC.emit(self.dev, info, True)

    def run(self):
        """Run in thread"""

        try:
            self._result = self.rip()
        except Exception as err:
            self.log.exception(
                "%s - Failed to rip title: %s",
                self.source[1],
                err,
            )

        self.FINISHED.emit(self.output)

    def rip(self):
        """
        Backup disc then extract titles

        Create a decrypted backup of the disc and then extract the requested
        titles. In most cases this will be faster than re-running makemkvcon
        for each title as there can be signifcant time spent scanning the disc
        to determine the layout of titles.

        Returns:
            bool : True if ripped, False otherwise

        """

        self.log.debug('%s - Running rip disc', self.dev)

        # If output already exists, then delete it
        if os.path.exists(self.output):
            try:
                os.remove(self.output)
            except IsADirectoryError:
                shutil.rmtree(self.output)
            except FileNotFoundError:
                pass

        # Start process for backup
        self.makemkvcon()

        # Need option for full disc
        self.progress.MKV_NEW_PROCESS.emit(
            self.dev,
            self.proc,
            self.pipe,
        )

        # Wait for process to finish
        self.monitor_proc()

        # Eject the disc if _eject set
        if self._eject:
            self.EJECT_DISC.emit()

        # If bad return code or failure
        if self.returncode != 0 or self.failure:
            self.FAILURE.emit(self.output)
            self.log.warning("%s - Error backing up disc", self.dev)

            try:
                os.remove(self.output)
            except IsADirectoryError:
                shutil.rmtree(self.output)
            except FileNotFoundError:
                pass
            self.log.debug("%s - Removed dir: %s", self.dev, self.output)
            return False

        self.SUCCESS.emit(self.output)
        return True


class ExtractFromDVD(makemkv.MakeMKVRip):
    """
    Extract a title from a DVD backup

    """

    def __init__(self, src: str, paths: dict, tmpdir: str, progress):
        """
        Extract a given title from a DVD backup

        Arguments:
            src (str): Path to DVD backup iso
            paths (dict): Dictionary with keys indicating title to extract
                and values file to extract/move to
            tmpdir (str): Temporary directory to extract titles to
            progress: Progress widget

        """

        title = tuple(paths.keys())[0]
        super().__init__(
            'mkv',
            title=title,
            iso=src,
            output=tmpdir,
        )

        self.src = src
        self.paths = paths
        self.progress = progress

    def run(self):
        """Run in thread"""

        try:
            self._result = self.extract()
        except Exception as err:
            self.log.exception(
                "%s - Failed to rip title: %s",
                self.source[1],
                err,
            )

        output = self.paths.pop(self.title)  # Remove reference to title here
        self.FINISHED.emit(output)

    def extract(self):
        self.log.debug('%s - Running extract title', self.src)

        # Get output path for file
        output = self.paths[self.title]

        if os.path.isfile(output):
            self.log.warning(
                "%s - Output file already exists, skipping: %s",
                self.src,
                output,
            )
            return

        # If progress is set, then update current track
        self.progress.MKV_CUR_TRACK.emit(self.src, self.title)

        # Start the extract process
        self.makemkvcon()

        self.progress.MKV_NEW_PROCESS.emit(
            self.src,
            self.proc,
            self.pipe,
        )

        self.monitor_proc()  # Wait for process to finish

        # Get base name of the source file and then get all files in the
        # output directory that are NOT then source file
        fname = os.path.basename(self.src)
        files = [
            os.path.join(self.output, item)
            for item in os.listdir(self.output)
            if item != fname
        ]

        # If there was an error during extration
        if self.returncode != 0 or self.failure:
            self.FAILURE.emit(output)
            self.log.warning(
                "%s - Failed to extract title %s from backup",
                self.src,
                self.title,
            )
            if len(files) > 0:
                for file in files:
                    os.remove(file)

            return False

        # If number of files found is different that one (1)
        if len(files) != 1:
            self.FAILURE.emit(output)
            self.log.error("%s - Too many output files!", self.src)
            for fname in files:
                os.remove(fname)
            return False

        # Rename/move the extracted file to where it should be
        self.log.info(
            "%s - Renaming file '%s' ---> '%s'",
            self.src,
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

        self.SUCCESS.emit(output)

        return True


class ExtractFromBluRay(QtCore.QThread):
    """
    Extract title from BluRay backup

    """

    FAILURE = QtCore.pyqtSignal(str)
    SUCCESS = QtCore.pyqtSignal(str)
    FINISHED = QtCore.pyqtSignal(str)

    def __init__(self, src: str, paths: dict, info: dict, progress):
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

        super().__init__()

        self.log = logging.getLogger(__name__)
        self._result = None

        self.src = src
        self.paths = paths
        self.info = info
        self.progress = progress
        self.title = tuple(self.paths.keys())[0]

    @property
    def result(self):
        return self._result

    def run(self):
        """Run thread"""

        try:
            self._result = self.extract()
        except Exception as err:
            self.log.exception(
                "%s - Failed to rip title: %s",
                self.src,
                err,
            )

        output = self.paths.pop(self.title)  # Remove reference to title here
        self.FINISHED.emit(output)

    def extract(self):
        # Try to get preferred language from MakeMKV settings and set
        # lang_opts if found
        lang = MAKEMKV_SETTINGS.get('app_PreferredLanguage', None)
        if lang is not None:
            lang_opts = [
                '--default-language', lang,
                '--audio-tracks', lang,
                '--subtitle-tracks', lang,
            ]

        output = self.paths[self.title]
        if os.path.isfile(output):
            self.log.warning(
                "%s - Output file already exists, skipping: %s",
                self.src,
                output,
            )
            return

        # Try to get the source playlist/stream for the title
        title_src = (
            self
            .info
            .get('titles', {})
            .get(self.title, {})
            .get('Source FileName', None)
        )
        if title_src is None:
            self.FAILURE.emit(output)
            self.log.error(
                "%s - Failed to find playlist name for title '%s', "
                "skipping.",
                self.src,
                self.title,
            )
            return False

        # Build full path to file based on extension
        if title_src.endswith(PLAYLIST_EXT):
            title_src = os.path.join(self.src, *PLAYLIST_DIR, title_src)
        elif title_src.endswith(STREAM_EXT):
            title_src = os.path.join(self.src, *STREAM_DIR, title_src)
        else:
            self.FAILURE.emit(output)
            self.log.warning(
                "%s - File not currently supported: %s",
                self.src,
                title_src,
            )
            return False

        # Build mkvmerge command to run
        cmd = [MKVMERGE, '-o', output]
        if lang is not None:
            cmd.extend(lang_opts)
        cmd.append(title_src)

        self.log.debug("%s - Running command: %s", self.src, cmd)
        self.proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            universal_newlines=True,
        )

        # Set current track on progress
        self.progress.MKV_CUR_TRACK.emit(self.src, self.title)
        self.progress.MKV_NEW_PROCESS.emit(self.src, self.proc, 'stdout')
        self.proc.wait()

        if self.proc.returncode != 0:
            self.FAILURE.emit(output)
            return False

        self.SUCCESS.emit(output)
        return True
