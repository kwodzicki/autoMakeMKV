import logging

from PyQt5 import QtWidgets
from PyQt5 import QtCore

from .. import NAME
from .. import makemkv
from ..path_utils import CONVENTIONS
from . import utils
from . import base_widgets
from . import dialogs
from . import progress

SIZEKEY = 'Disk Size (Bytes)'

BACKUP_THEN_TAG = 4
RIP = 3
SAVE = 2
OPEN = 1
IGNORE = 0


class DiscMetadataEditor(dialogs.MyQDialog):

    DEFAULT_TITLE = 'Title'

    def __init__(
        self,
        dev: str,
        hashid: str,
        dbdir: str,
        *args,
        discInfo: dict | None = None,
        titles: dict | None = None,
        load_existing: bool = False,
        backed_up: bool = False,
        **kwargs,
    ):

        super().__init__(*args, **kwargs)

        self.log = logging.getLogger(__name__)
        self.curTitle = None
        self.discLabel = None
        self.info = None
        self.loadDisc = None
        self._discInfo = discInfo or dict()
        self._titles = titles or dict()

        self.dev = dev
        self.hashid = hashid
        self.dbdir = dbdir
        self.load_existing = load_existing

        self.vendor, self.model = utils.get_vendor_model(dev)
        self.setWindowTitle()

        self.titleTree = QtWidgets.QTreeWidget()
        self.titleTree.setHeaderLabels(['Type', 'Description'])
        self.titleTree.setColumnWidth(0, 100)

        # Initialize basic progress widget
        self.progress = progress.BasicProgressWidget(dev, pipe='stderr')

        self.infoBox = QtWidgets.QTextEdit()
        self.msgs = QtWidgets.QTextEdit()
        self.save_but = QtWidgets.QPushButton('Save && Eject')
        self.backup_tag = QtWidgets.QPushButton('Backup Then Tag')
        self.rip_but = QtWidgets.QPushButton('Save && Rip')

        self.save_but.clicked.connect(self.save)
        self.save_but.setEnabled(False)

        self.backup_tag.clicked.connect(self.backup_then_tag)
        self.backup_tag.setEnabled(False)

        self.rip_but.clicked.connect(
            lambda *args, **kwargs: self.save(*args, rip=True, **kwargs)
        )
        self.rip_but.setEnabled(False)

        self.msgs.setReadOnly(True)

        self.discMetadata = base_widgets.DiscMetadata()
        self.titleMetadata = base_widgets.TitleMetadata()
        self.titleMetadata.connect_parent(self.discMetadata)

        layout = QtWidgets.QGridLayout()
        layout.setColumnStretch(0, 3)
        layout.setColumnStretch(1, 2)
        layout.addWidget(self.discMetadata, 0, 0, 1, 2)
        layout.addWidget(self.titleTree, 1, 0, 2, 1)
        layout.addWidget(self.infoBox, 1, 1, 1, 1)
        layout.addWidget(self.titleMetadata, 2, 1, 1, 1)
        layout.addWidget(self.msgs, 3, 0, 1, 2)
        layout.addWidget(self.progress, 4, 0, 1, 2)
        layout.addWidget(self.save_but, 5, 0, 1, 2)
        # If disc has NOT been backed up, then add button
        if not backed_up:
            layout.addWidget(self.backup_tag, 6, 0, 1, 2)
        layout.addWidget(self.rip_but, 7, 0, 1, 2)

        layout.setMenuBar(
            self._initMenu()
        )

        self.setLayout(layout)
        self.resize(720, 720)

        if len(self.discInfo) == 0 or len(self.titles) == 0:
            self.loadDisc = makemkv.MakeMKVInfo(
                dev,
                self.hashid,
                dbdir=self.dbdir,
            )
            self.loadDisc.FAILURE.connect(self.load_failed)
            self.loadDisc.SIGNAL.connect(self.msgs.append)
            self.loadDisc.finished.connect(self.buildTitleTree)

            self.log.info("Loading new disc")
            self.loadDisc.start()
            self.loadDisc.started.wait()
            # Update process to read from in the progress widget
            # self.progress.new_process(self.loadDisc.proc)
            self.progress.NEW_PROCESS.emit(self.loadDisc.proc, 'stderr')
        else:
            self.buildTitleTree()

        self.show()

    def _initMenu(self):

        self.log.debug('Initializing menu')
        menu_bar = QtWidgets.QMenuBar()  # self.menuBar()

        file_menu = menu_bar.addMenu("File")

        action_save = QtWidgets.QAction("&Save", self)
        action_save.triggered.connect(self.save)
        action_quit = QtWidgets.QAction("&Cancel", self)
        action_quit.triggered.connect(self.quit)

        file_menu.addAction(action_save)
        file_menu.addSeparator()
        file_menu.addAction(action_quit)
        return menu_bar

    @QtCore.pyqtProperty(dict)
    def discInfo(self) -> dict:
        if self.loadDisc is None:
            return self._discInfo
        return self.loadDisc.discInfo

    @QtCore.pyqtProperty(dict)
    def titles(self) -> dict:
        if self.loadDisc is None:
            return self._titles
        return self.loadDisc.titles

    @QtCore.pyqtSlot(str)
    def load_failed(self, device: str):

        dialog = dialogs.RipFailed(device)
        dialog.exec_()

    def quit(self, *args, **kwargs):
        if self.loadDisc:
            self.loadDisc.quit()
        self.accept()

    def setWindowTitle(self):

        title = f"{self.dev} [{self.hashid}]"
        if self.vendor and self.model:
            title = f"{self.vendor} {self.model}: {title}"
        if self.discLabel:
            title = f"{title} - {self.discLabel}"
        super().setWindowTitle(title)

    def save(self, *args, **kwargs):
        """
        Run when 'Save' button is clicked

        Loop over all items in the QTreeWidget.
        Any items that do NOT have default name,
        flag as actual titles to be ripped

        """

        self.log.debug('Saving data JSON')

        info = self.discMetadata.getInfo()
        if info is None:
            self.log.debug('No disc metadata')
            return

        titles = self.getTitleInfo()
        if titles is None:
            return

        if len(titles) == 0:
            self.log.info('No titles marked for ripping!')
            message = QtWidgets.QMessageBox()
            res = message.warning(
                self,
                'No titles selected',
                'No titles have been selected for ripping. '
                'Please select some titles and try again',
            )
            return

        info['titles'] = titles

        message = QtWidgets.QMessageBox()
        res = message.question(
                self,
                '',
                'Are you sure the information is correct?',
                message.Yes | message.No
        )
        if res == message.Yes:
            utils.save_metadata(
                info,
                self.hashid,
                dbdir=self.dbdir,
                replace=True,
            )
            self.info = info
            self.done(RIP if kwargs.get('rip', False) else SAVE)

    def backup_then_tag(self, *args, **kwargs):
        """
        Backup the disc, then reopen for tagging

        If it is unclear what titles are what on the disc, namely for Blu-ray
        discs, we can backup the disc and then inspect the various files and
        playlists to determine what is what. Then, we can use that information
        to tag the disc and extract what we want!

        """
        self.log.debug('Saving data JSON')

        info = self.discMetadata.getInfo()
        if info is None:
            self.log.debug('No disc metadata')
            return

        titles = self.getTitleInfo()
        info['titles'] = {} if titles is None else titles

        message = QtWidgets.QMessageBox()
        res = message.question(
                self,
                '',
                'Are you sure you want to run a full disc backup and then '
                'tag the metadata afterwards?\n\n'
                'This option is useful when it is unclear which title is '
                'which, allowing you to inspect the backup while tagging '
                'the disc.\n\n'
                'Note that titles will simply be extracted from disc after '
                'metadata is entered; no need to re-backup the disc.',
                message.Yes | message.No
        )
        if res == message.Yes:
            utils.save_metadata(
                info,
                self.hashid,
                dbdir=self.dbdir,
                replace=True,
            )
            self.info = info
            self.done(BACKUP_THEN_TAG)

    def getTitleInfo(self) -> dict | None:
        """
        Get information about which titles to extract

        """

        if self.curTitle is not None:
            self.curTitle.info.update(
                self.titleMetadata.getInfo()
            )

        titles = {}
        root = self.titleTree.invisibleRootItem()
        for i in range(root.childCount()):
            titleObj = root.child(i)  # Get the object from the QTreeWidget
            if titleObj.checkState(0) == 0:
                continue

            if not check_info(self, titleObj.info):
                return

            titles[titleObj.titleID] = titleObj.info

        return titles

    def selectTitle(self, obj, col):
        """
        Run when object in Tree is selected

        When an object in the QTree is selected,
        update the information text box with info
        about the title/stream/etc.

        Argumments:
            obj : Reference to the QTreeWidget object that
                has been selected
            col : The column number of the object in the
                QTreeWidget

        Returns:
            None.

        """

        self.infoBox.clear()  # Clear title/stream info box
        # Iterate over makeMKVInfo for the title/stream
        for key, val in obj.makeMKVInfo.items():
            # Format data and write to info box
            self.infoBox.append(f"{key} : {val}")

        # If NOT title object
        if not obj.isTitle:
            return

        if self.curTitle is not None:  # If current title IS set
            # Update the 'current' object with information from
            # the titleMetadata pane
            self.curTitle.info.update(
                self.titleMetadata.getInfo()
            )
        # Set curTitle title actual currently selected title
        self.curTitle = obj
        for key, val in self.discMetadata.getInfo().items():
            if (val == ''):
                continue
            if (key not in obj.info) or (obj.info[key] == ''):
                obj.info[key] = val

        # Update the titleMetadata pane with information from
        # actual current title
        self.titleMetadata.setInfo(obj.info)

    def buildTitleTree(self, info=None):

        # Remove the progress widget from the window if exists
        if self.progress is not None:
            self.layout().removeWidget(self.progress)
            self.progress.deleteLater()
            self.progress = None

        self.titleTree.clear()
        discInfo = self.discInfo
        titles = self.titles
        infoTitles = {}

        if self.load_existing:
            info = utils.load_metadata(
                self.dev,
                hashid=self.hashid,
                dbdir=self.dbdir,
            )

        if info is not None:
            self.hashid = info.get('hashID', self.hashid)
            self.discMetadata.setInfo(info)
            infoTitles = info['titles']

        self.discLabel = discInfo.get('Name', None)
        self.setWindowTitle()

        # NOTE create nested data
        for titleID, titleInfo in titles.items():
            title = QtWidgets.QTreeWidgetItem(self.titleTree)
            title.setCheckState(0, 0)
            title.makeMKVInfo = titleInfo
            title.isTitle = True
            title.titleID = titleID
            if titleID in infoTitles:
                title.info = infoTitles[titleID]
                title.setCheckState(0, 2)
            else:
                keys = ['Source Title Id', 'Source FileName', 'Segments Map']
                title.info = self.titleMetadata.getInfo()
                title.info.update(
                    {key: titleInfo.get(key, '') for key in keys}
                )

            # Used to update old files to contain the Segments Map
            # if 'Segments Map' not in title.info:
            #    title.info['Segments Map'] = titleInfo['Segments Map']
            title.setText(0, self.DEFAULT_TITLE)
            title.setText(1, titleInfo.get('Tree Info', '??Tree Info??'))

            title.setFlags(title.flags() | QtCore.Qt.ItemIsUserCheckable)

            for streamID, streamInfo in titleInfo.pop('streams', {}).items():
                child = QtWidgets.QTreeWidgetItem(title)
                child.makeMKVInfo = streamInfo
                child.isTitle = False
                child.info = {}
                child.setText(0, streamInfo.get('Type' '??Type??'))
                child.setText(1, streamInfo.get('Tree Info', '??Tree Info??'))

        # Run given method one object in QTreeWidget is clicked
        self.titleTree.currentItemChanged.connect(self.selectTitle)
        # Enable buttons after the tree is populated
        self.save_but.setEnabled(True)
        self.backup_tag.setEnabled(True)
        self.rip_but.setEnabled(True)


class ExistingDiscOptions(dialogs.MyQDialog):
    """
    Dialog with timeout for discs in database

    When a disc is inserted, a check is done to see if the disc
    exisis in the disc database. If the disc does exist, this
    dialog should be shown to give the use some options for what
    to do; save/rip the disc, open the disc metadata for editing,
    or just ignore the disc all together.

    To enable user-less interaction, however, the dialog has a
    timeout feature that automatically selects save/rip disc
    after a certain amount of time. This way, the user can
    just insert discs and forget about them (assuming they are in
    the database) or do other things.

    """

    def __init__(
        self,
        dev: str,
        info: dict,
        convention: str,
        extras: bool,
        everything: bool,
        timeout: int = 30,
        parent=None,
    ):
        super().__init__(
            parent=parent,
            timeout=timeout,
            timeout_code=RIP,
            timeout_fmt="Disc will begin ripping in: {:>4d} seconds"
        )

        self.setMinimumSize(480, 480)
        self.dev = dev
        self.extras = extras
        self.everything = everything

        qbtn = (
            QtWidgets.QDialogButtonBox.Save
            | QtWidgets.QDialogButtonBox.Open
            | QtWidgets.QDialogButtonBox.Ignore
        )
        self.button_box = QtWidgets.QDialogButtonBox(qbtn)
        self.button_box.addButton(
            'Wait',
            QtWidgets.QDialogButtonBox.HelpRole,
        )
        self.button_box.clicked.connect(self.action)

        message = (
            "The inserted disc has been found in the database.\n"
            "Would you like to:\n\n"
            "\tSave: Rip titles to computer (default)\n"
            "\tOpen: Open the disc metadata for editing.\n"
            "\tIgnore: Ignore the disc and do nothing?\n"
        )

        self.timeout_label.setText(
            self.timeout_fmt.format(self.timeout)
        )

        self.convention_label = QtWidgets.QLabel('Output naming convention:')
        self.convention_box = QtWidgets.QComboBox()
        self.convention_box.addItems(CONVENTIONS)
        idx = self.convention_box.findText(convention)
        if idx != -1:
            self.convention_box.setCurrentIndex(idx)

        # Set up model for table containing releases
        self.model = MyTableModel(info, self.extras, self.everything)

        # Build the table
        self.table = QtWidgets.QTableView()
        self.table.setModel(self.model)
        # Hide row names
        self.table.verticalHeader().setVisible(False)
        # Resize checkbox column
        self.table.resizeColumnToContents(0)
        # Disable selection
        self.table.setSelectionMode(QtWidgets.QTableView.NoSelection)
        self.table.setFocusPolicy(QtCore.Qt.NoFocus)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(
            QtWidgets.QLabel(message)
        )
        layout.addWidget(self.timeout_label)
        layout.addWidget(self.table)
        layout.addWidget(self.convention_label)
        layout.addWidget(self.convention_box)
        layout.addWidget(self.button_box)

        self.setLayout(layout)
        vendor, model = utils.get_vendor_model(self.dev)
        self.setWindowTitle(f"{NAME} - {vendor} {model}")

        self.start_timer()
        self.open()

    @property
    def convention(self) -> str:
        return self.convention_box.currentText()

    @property
    def checked(self) -> list[bool]:
        return self.model.checked

    def action(self, button):
        """
        Button action handler

        """

        self.stop_timer()

        # If button has HelpRole, then erase timer label and return
        role = self.button_box.buttonRole(button)
        if role == QtWidgets.QDialogButtonBox.HelpRole:
            self.timeout_label.setText('')
            return

        if button == self.button_box.button(QtWidgets.QDialogButtonBox.Save):
            self.done(RIP)
            return
        if button == self.button_box.button(QtWidgets.QDialogButtonBox.Open):
            self.done(OPEN)
            return
        self.done(IGNORE)


class MyTableModel(QtCore.QAbstractTableModel):
    """
    Table model for release information

    """

    def __init__(
        self,
        info: dict,
        extras: bool,
        everything: bool,
        parent=None,
    ):
        super().__init__(parent)

        self.log = logging.getLogger(__name__)

        self.extras = extras
        self.everything = everything

        self.info = info
        # Column names
        self.series_columns = [
            'Series',
            'Year',
            'Season',
            'Episode',
            'Title',
            'Extra Type',
        ]

        self.movie_columns = [
            'Movie',
            'Year',
            'Extra Type',
            'Extra Title',
        ]

        self.mixed_columns = [
            'Movie/Series',
            'Year',
            'Season',
            'Episode',
            'Title',
            'Extra Type',
            'Extra Title',
        ]

        self.columns = None
        self._checked = []
        self._data = []
        self._build_data()

    @property
    def checked(self) -> list[bool]:
        return self._checked

    def _is_checked(self, extra: str) -> bool:
        """
        Test if row should be checked by default

        Arguments:
            extra (str): Value of the extra type

        Returns:
            bool: If True, then checked, if False, unchecked

        """

        # Extra types to not consider as extras
        non_extra = ('edition', '')
        return (
            self.everything
            or (extra in non_extra and not self.extras)
            or (extra not in non_extra and self.extras)
        )

    def _build_data(self):
        """
        Build data for table display

        Iterate to create table rows and flattend information for releases.
        The flattened release informaiton is created by expanding each
        medium object in the list of mediums for a release into its own
        "release" object.

        """

        titles = self.info.get('titles', {})

        # Check each title to see if disc is mix of movies/series
        series = False
        movie = False
        for title in titles.values():
            if not series:
                series = title.get('isSeries', False)
            if not movie:
                movie = title.get('isMovie', False)

        # Set column names and row information builder based on movie/series
        if series and movie:
            func = self._mixed_info
            self.columns = self.mixed_columns
        elif series:
            func = self._series_info
            self.columns = self.series_columns
        elif movie:
            func = self._movie_info
            self.columns = self.movie_columns
        else:
            self.log.error("Could not determine if movie or series!")
            return

        # Loop over each title and build data for table
        data = []
        checked = []
        for title in titles.values():
            check, *info = func(title)
            checked.append(check)
            data.append(info)

        self._checked.extend(checked)
        self._data.extend(data)

    def _series_info(self, title: dict) -> tuple:
        """
        Build table row for series disc

        Arguments:
            title (dict): Information about a single title on the disc

        Returns:
            tuple: Bool value for if title should be ripped based on the
                extras/everything global settings and then all information
                to be presented in the table
        """

        extra = title.get('extra', '')

        return (
            self._is_checked(extra),
            title.get('title', ''),
            title.get('year', ''),
            title.get('season', ''),
            title.get('episode', ''),
            title.get('episodeTitle', ''),
            extra,
        )

    def _movie_info(self, title: dict) -> tuple:
        """
        Build table row for movie disc

        Arguments:
            title (dict): Information about a single title on the disc

        Returns:
            tuple: Bool value for if title should be ripped based on the
                extras/everything global settings and then all information
                to be presented in the table
        """

        extra = title.get('extra', '')

        return (
            self._is_checked(extra),
            title.get('title', ''),
            title.get('year', ''),
            extra,
            title.get('extraTitle'),
        )

    def _mixed_info(self, title: dict) -> tuple:
        """
        Build table row for mixed movie/series disc

        Arguments:
            title (dict): Information about a single title on the disc

        Returns:
            tuple: Bool value for if title should be ripped based on the
                extras/everything global settings and then all information
                to be presented in the table
        """

        extra = title.get('extra', '')

        return (
            self._is_checked(extra),
            title.get('title', ''),
            title.get('year', ''),
            title.get('season', ''),
            title.get('episode', ''),
            title.get('episodeTitle', ''),
            extra,
            title.get('extraTitle'),
        )

    def headerData(
        self,
        section: int,
        orientation: QtCore.Qt.Orientation,
        role: int,
    ):
        if role == QtCore.Qt.DisplayRole:
            if section == 0:
                return ""
            if orientation == QtCore.Qt.Horizontal:
                return self.columns[section - 1]
            return ""

    def columnCount(self, parent=None):
        if self.rowCount() == 0:
            return 0
        return len(self._data[0]) + 1

    def rowCount(self, parent=None):
        return len(self._data)

    def data(self, index: QtCore.QModelIndex, role: int):
        row, col = index.row(), index.column()

        if col == 0:
            if role == QtCore.Qt.CheckStateRole:
                return (
                    QtCore.Qt.Checked
                    if self._checked[row] else
                    QtCore.Qt.Unchecked
                )
            if role == QtCore.Qt.DisplayRole:
                return ""
            return QtCore.QVariant()

        if role == QtCore.Qt.DisplayRole:
            return str(self._data[row][col - 1])

        return QtCore.QVariant()

    def setData(self, index, value, role=QtCore.Qt.EditRole):
        row, col = index.row(), index.column()
        if col == 0 and role == QtCore.Qt.CheckStateRole:
            self._checked[row] = (value == QtCore.Qt.Checked)
            self.dataChanged.emit(index, index, [QtCore.Qt.CheckStateRole])
            return True
        return False

    def flags(self, index):
        if index.column() == 0:
            return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsUserCheckable
        return QtCore.Qt.ItemIsEnabled


def check_info(parent, info: dict):
    """
    Check required disc metadata entered

    """

    message = None
    if not info['isMovie'] and not info['isSeries']:
        message = "Must select 'Movie' or 'Series'"
    elif info['isMovie'] and info['tmdb'] == '':
        message = "Must set TMDb ID"
    elif info['isSeries'] and info['tvdb'] == '':
        message = "Must set TVDb ID"
    elif info['title'] == '':
        message = "Must set Movie/Series Title"
    elif info['year'] == '':
        message = "Must set Movie/Series release year"
    elif ('media_type' in info) and (info['media_type'] == ''):
        message = "Must set media type!"

    if message is None:
        return True

    box = QtWidgets.QMessageBox(parent)
    box.setText(message)
    box.exec_()
    return False
