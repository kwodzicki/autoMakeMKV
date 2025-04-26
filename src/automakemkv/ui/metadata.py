import logging

from PyQt5 import QtWidgets
from PyQt5 import QtCore

from .. import NAME
from .. import makemkv
from . import utils
from . import base_widgets
from . import dialogs
from . import progress

SIZEKEY = 'Disk Size (Bytes)'

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
        load_existing: bool = False,
        **kwargs,
    ):

        super().__init__(*args, **kwargs)

        self.log = logging.getLogger(__name__)
        self.curTitle = None
        self.discLabel = None
        self.info = None
        self.sizes = None

        self.dev = dev
        self.hashid = hashid
        self.dbdir = dbdir
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
        self.rip_but = QtWidgets.QPushButton('Save && Rip')
        self.save_but.clicked.connect(self.save)
        self.save_but.setEnabled(False)

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
        layout.addWidget(self.rip_but, 6, 0, 1, 2)

        layout.setMenuBar(
            self._initMenu()
        )

        self.setLayout(layout)
        self.resize(720, 720)

        self.loadDisc = makemkv.MakeMKVInfo(
            dev,
            hashid,
            dbdir=self.dbdir,
        )
        self.loadDisc.FAILURE.connect(self.load_failed)
        self.loadDisc.SIGNAL.connect(self.msgs.append)
        self.loadDisc.finished.connect(self.buildTitleTree)

        if load_existing:
            self.log.info("Loading existing information")
            path = utils.file_from_id(self.hashid, dbdir=self.dbdir)
            self.loadDisc.loadFile(json=path)
            self.buildTitleTree(
                *utils.load_metadata(hashid=self.hashid, dbdir=self.dbdir)
            )
        else:
            self.log.info("Loading new disc")
            self.loadDisc.start()
            self.loadDisc.started.wait()
            # Update process to read from in the progress widget
            # self.progress.new_process(self.loadDisc.proc)
            self.progress.NEW_PROCESS.emit(self.loadDisc.proc, 'stderr')

        self.show()

    def _initMenu(self):

        self.log.debug('Initializing menu')
        menu_bar = QtWidgets.QMenuBar()  # self.menuBar()

        file_menu = menu_bar.addMenu("File")

        action_open = QtWidgets.QAction("&Open...", self)
        action_open.triggered.connect(self.open)
        action_save = QtWidgets.QAction("&Save", self)
        action_save.triggered.connect(self.save)
        action_quit = QtWidgets.QAction("&Cancel", self)
        action_quit.triggered.connect(self.quit)

        file_menu.addAction(action_open)
        file_menu.addAction(action_save)
        file_menu.addSeparator()
        file_menu.addAction(action_quit)
        return menu_bar

    @QtCore.pyqtSlot(str)
    def load_failed(self, device: str):

        dialog = dialogs.RipFailed(device)
        dialog.exec_()

    def quit(self, *args, **kwargs):
        self.loadDisc.quit()
        self.accept()

    def setWindowTitle(self):

        title = f"{self.dev} [{self.hashid}]"
        if self.vendor and self.model:
            title = f"{self.vendor} {self.model}: {title}"
        if self.discLabel:
            title = f"{title} - {self.discLabel}"
        super().setWindowTitle(title)

    def open(self, *args, **kwargs):

        self.log.debug('Attempting to open disc JSON for editing')
        dialog = QtWidgets.QFileDialog(directory=self.dbdir)
        dialog.setDefaultSuffix('json')
        dialog.setNameFilters(['JSON (*.json)'])
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return

        files = dialog.selectedFiles()
        if len(files) != 1:
            box = QtWidgets.QMessageBox(self)
            box.setText('Can only select one (1) file')
            box.exec_()
            return

        self.msgs.clear()
        self.loadDisc.loadFile(json=files[0])
        self.buildTitleTree(
            *utils.load_metadata(fpath=files[0])
        )

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

        if self.curTitle is not None:
            self.curTitle.info.update(
                self.titleMetadata.getInfo()
            )

        titles = {}
        sizes = {}
        root = self.titleTree.invisibleRootItem()
        for i in range(root.childCount()):
            titleObj = root.child(i)  # Get the object from the QTreeWidget
            if titleObj.checkState(0) == 0:
                continue

            if not check_info(self, titleObj.info):
                return

            titles[titleObj.titleID] = titleObj.info
            sizes[titleObj.titleID] = int(
                titleObj.makeMKVInfo.get(SIZEKEY, '0')
            )

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
            self.sizes = sizes
            self.done(RIP if kwargs.get('rip', False) else SAVE)

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

    def buildTitleTree(self, info=None, sizes=None):

        # Remove the progress widget from the window
        self.layout().removeWidget(self.progress)
        self.progress.deleteLater()

        self.titleTree.clear()
        discInfo = self.loadDisc.discInfo
        titles = self.loadDisc.titles
        infoTitles = {}
        if info is not None:
            self.hashid = info.get('hashID', None)
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
        # Enable 'Apply' Button after the tree is populated
        self.save_but.setEnabled(True)
        # Enable 'Apply' Button after the tree is populated
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

    def __init__(self, dev: str, info: dict, timeout: int = 30, parent=None):
        super().__init__(parent)

        self.dev = dev
        self._timeout = timeout
        qbtn = (
            QtWidgets.QDialogButtonBox.Save
            | QtWidgets.QDialogButtonBox.Open
            | QtWidgets.QDialogButtonBox.Ignore
        )
        self.button_box = QtWidgets.QDialogButtonBox(qbtn)
        self.button_box.clicked.connect(self.action)

        message = (
            "The inserted disc has been found in the database.\n"
            "Would you like to:\n\n"
            "\tSave: Rip titles to computer (default)\n"
            "\tOpen: Open the disc metadata for editing.\n"
            "\tIgnore: Ignore the disc and do nothing?\n"
        )

        self.timeout_fmt = "Disc will begin ripping in: {:>4d} seconds"
        self.timeout_label = QtWidgets.QLabel(
            self.timeout_fmt.format(self._timeout)
        )

        # Set up model for table containing releases
        self.model = MyTableModel(info)

        # Build the table
        self.table = QtWidgets.QTableView()
        self.table.setModel(self.model)
        # Hide row names
        self.table.verticalHeader().setVisible(False)
        # Disable selection
        self.table.setSelectionMode(QtWidgets.QTableView.NoSelection)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(
            QtWidgets.QLabel(message)
        )
        layout.addWidget(self.timeout_label)
        layout.addWidget(self.table)
        layout.addWidget(self.button_box)

        self.setLayout(layout)
        vendor, model = utils.get_vendor_model(self.dev)
        self.setWindowTitle(f"{NAME} - {vendor} {model}")

        self._timer = QtCore.QTimer()
        self._timer.timeout.connect(self._message_timeout)
        self._timer.start(1000)
        self.open()

    def _message_timeout(self):
        self._timeout -= 1
        if self._timeout > 0:
            self.timeout_label.setText(
                self.timeout_fmt.format(self._timeout)
            )
            return
        self._timer.stop()
        self.done(RIP)

    def action(self, button):
        self._timer.stop()
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

    def __init__(self, info: dict, parent=None):
        super().__init__(parent)

        self.log = logging.getLogger(__name__)

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

        self.columns = None
        self._build_data()

    def _build_data(self):
        # Iterate to create table rows and flattend information for releases.
        # The flattened release informaiton is created by expanding each
        # medium object in the list of mediums for a release into its own
        # "release" object.

        if self.info.get('isSeries', False):
            func = self._series_info
            self.columns = self.series_columns
        elif self.info.get('isMovie', False):
            func = self._movie_info
            self.columns = self.movie_columns
        else:
            self.log.error("Could not determine if movie or series!")
            return

        data = []
        for title in self.info.get('titles', {}).values():
            data.append(func(title))

        self.data = data

    def _series_info(self, title):

        return (
            self.info.get('title', ''),
            self.info.get('year', ''),
            title.get('season', ''),
            title.get('episode', ''),
            title.get('episodeTitle', ''),
            title.get('extra', ''),
        )

    def _movie_info(self, title):

        return (
            self.info.get('title', ''),
            self.info.get('year', ''),
            title.get('extra', ''),
            title.get('extraTitle'),
        )

    def headerData(
        self,
        section: int,
        orientation: QtCore.Qt.Orientation,
        role: int,
    ):
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return self.columns[section]
            return ""

    def columnCount(self, parent=None):
        return len(self.data[0])

    def rowCount(self, parent=None):
        return len(self.data)

    def data(self, index: QtCore.QModelIndex, role: int):
        if role == QtCore.Qt.DisplayRole:
            row = index.row()
            col = index.column()
            return str(self.data[row][col])


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
