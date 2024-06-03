import logging
import os

from PyQt5 import QtCore, QtWidgets, QtGui, Qt

from ..makemkv import MakeMKVInfo
from .utils import DBDIR, checkInfo, getDiscID, loadData, saveData

EXTRATYPES = [ 
    'behindthescenes',
    'deleted',
    'featurette',
    'interview',
    'scene',
    'short',
    'trailer',
    'other',
]

MOVIETYPES   = ['edition']
SERIESTYPES  = ['']
CONTENTTYPES = ['', 'Movie', 'Series']
MEDIATYPES   = [
    'DVD',
    'Blu-Ray',
    '4K Blu-Ray (UHD)',
]

SIZEKEY = 'Disk Size (Bytes)'

SAVE = 2
OPEN = 1
IGNORE = 0



class BaseMetadata( QtWidgets.QWidget ):
    """
    Widget for disc metadata

    This widget is for entering metadata that
    pertains to the entire disc such as 
    Movie/Series name, database IDs 
    (e.g. TMDb, TVDb, IMDb), and release/
    first aired year.

    """

    def __init__(self, *args, **kwargs ):
        super().__init__(*args, **kwargs)

        self.log = logging.getLogger( __name__ )
        layout = QtWidgets.QGridLayout()

        self.title    = QtWidgets.QLineEdit()
        self.year     = QtWidgets.QLineEdit()
        self.tmdb     = QtWidgets.QLineEdit()
        self.tvdb     = QtWidgets.QLineEdit()
        self.imdb     = QtWidgets.QLineEdit()

        self.type     = QtWidgets.QComboBox( )
        self.type.addItems( CONTENTTYPES )

        self.title.setPlaceholderText( 'Movie/Series Title' )
        self.year.setPlaceholderText(  'Movie Released / Series First Aired' )
        self.tmdb.setPlaceholderText(  'TheMovieDb ID' )
        self.tvdb.setPlaceholderText(  'TheTVDb ID' )
        self.imdb.setPlaceholderText(  'IMDb ID' )

        layout.addWidget( self.title,     0, 0 )
        layout.addWidget( self.year,      1, 0 )

        # Build wiget for the type of video (Movie/TV) 
        _layout  = QtWidgets.QHBoxLayout()
        _layout.addWidget( QtWidgets.QLabel('Type : ') )
        _layout.addWidget( self.type )
        video_type = QtWidgets.QWidget()
        video_type.setLayout( _layout )

        layout.addWidget( video_type, 2, 0 )

        layout.addWidget( self.tmdb,     0, 1 )
        layout.addWidget( self.tvdb,     1, 1 )
        layout.addWidget( self.imdb,     2, 1 )
        
        self.setLayout( layout )

    def connect_parent(self, parent):
        """
        Connect all fields to parent

        Link all the entry fields to a parent object
        so that when text in parent is changed, it is changed
        in this object as well.

        Idea is to use this method to link the 'title' metadata
        fields to the 'disc' metadata fields. That way, if
        information applies to entire disc (e.g., IMDb ID), then
        that information will be updated for all titles.

        """

        parent.title.textChanged.connect( self.title.setText )
        parent.year.textChanged.connect( self.year.setText )
        parent.tmdb.textChanged.connect( self.tmdb.setText )
        parent.tvdb.textChanged.connect( self.tvdb.setText )
        parent.imdb.textChanged.connect( self.imdb.setText )
        parent.type.currentIndexChanged.connect(
            self.type.setCurrentIndex,
        )
 
    def isMovie(self):

        return self.type.currentText() == 'Movie'

    def isSeries(self):

        return self.type.currentText() == 'Series'

    def getInfo(self):
        """
        Return dict with info from entry boxes

        Collect text from the various entry
        fields into a dictionary. A check is
        run to ensure that any required metadata
        are entered before returning the data.
        If data are missing, None is returned.

        Arguments:
            None.

        Returns:
            dict,None : If metadata contains
                required information, a dict
                is returned, else None.

        """

        self.log.debug( 'Getting base metadata from widget' )
        return  {
            'title'      : self.title.text(),
            'year'       : self.year.text(),
            'tmdb'       : self.tmdb.text(),
            'tvdb'       : self.tvdb.text(),
            'imdb'       : self.imdb.text(),
            'isMovie'    : self.isMovie(),
            'isSeries'   : self.isSeries(),
        }

    def setInfo(self, info):

        self.log.debug( 'Setting disc metadata fro widget' )
        self.title.setText( info.get('title', '') )
        self.year.setText(  info.get('year',  '') ) 
        self.tmdb.setText(  info.get('tmdb',  '') ) 
        self.tvdb.setText(  info.get('tvdb',  '') ) 
        self.imdb.setText(  info.get('imdb',  '') )

        if info.get('isMovie', False):
            self.type.setCurrentText('Movie')
        elif info.get('isSeries', False):
            self.type.setCurrentText('Series')


class DiscMetadata( BaseMetadata ):
    """
    Widget for disc metadata

    This widget is for entering metadata that
    pertains to the entire disc such as 
    Movie/Series name, database IDs 
    (e.g. TMDb, TVDb, IMDb), and release/
    first aired year.

    """

    def __init__(self, *args, **kwargs ):
        super().__init__(*args, **kwargs)

        self.log = logging.getLogger( __name__ )

        layout   = self.layout() 
        self.upc = QtWidgets.QLineEdit()
        self.upc.setPlaceholderText( 'Universal Product Code' )

        # Build wiget for the type of media (DVD/BluRay/etc.) 
        self.media_type = QtWidgets.QComboBox()
        self.media_type.addItems( [''] + MEDIATYPES )

        _layout  = QtWidgets.QGridLayout()
        _layout.addWidget( QtWidgets.QLabel( 'Media : ' ), 0, 0 )
        _layout.addWidget( self.media_type, 0, 1 )
        media_type = QtWidgets.QWidget()
        media_type.setLayout( _layout )
        
        layout.addWidget( media_type, 3, 0)
        layout.addWidget( self.upc,      3, 1 )

    def getInfo(self):
        """
        Return dict with info from entry boxes

        Collect text from the various entry
        fields into a dictionary. A check is
        run to ensure that any required metadata
        are entered before returning the data.
        If data are missing, None is returned.

        Arguments:
            None.

        Returns:
            dict,None : If metadata contains
                required information, a dict
                is returned, else None.

        """

        self.log.debug( 'Getting disc metadata from widget' )
        info = super().getInfo()
        info['media_type'] = self.media_type.currentText()
        info['upc'       ] = self.upc.text()
        print(info)
        return info

    def setInfo(self, info):

        self.log.debug( 'Setting disc metadata fro widget' )
        super().setInfo(info)
        self.upc.setText( info.get('upc',   '') )
        self.media_type.setCurrentText( info.get('media_type', '') )

class TitleMetadata( BaseMetadata ):
    """
    Widget for metadata about a title

    This widget is designed to collect
    metadata for individual titles on the
    disc.

    """

    def __init__(self, *args, **kwargs ):
        super().__init__(*args, **kwargs)

        self.log = logging.getLogger( __name__ )
        layout = self.layout()

        self.seasonLabel, self.season = (
            self.initSeriesWidget('Season', 'Season number')
        )
        self.episodeLabel, self.episode = (
            self.initSeriesWidget('Episode', 'Episode number')
        )
        self.episodeTitleLabel, self.episodeTitle = (
            self.initSeriesWidget('Title', 'Episode Title')
        )

        layout.addWidget( self.seasonLabel,       10, 0 )
        layout.addWidget( self.season,            10, 1 )
        layout.addWidget( self.episodeLabel,      11, 0 )
        layout.addWidget( self.episode,           11, 1 )
        layout.addWidget( self.episodeTitleLabel, 12, 0 )
        layout.addWidget( self.episodeTitle,      12, 1 )

        self.extraLabel = QtWidgets.QLabel('Extra')
        self.extra      = QtWidgets.QComboBox()

        self.extraTitleLabel = QtWidgets.QLabel('Extra Title')
        self.extraTitle      = QtWidgets.QLineEdit()
        self.extraTitle.setPlaceholderText(
            "Label for 'Extra' type"
        )

        self.extraTitleLabel.setHidden( True )
        self.extraTitle.setHidden( True )

        layout.addWidget( self.extraLabel,      13, 0)
        layout.addWidget( self.extra,           13, 1)
        layout.addWidget( self.extraTitleLabel, 14, 0)
        layout.addWidget( self.extraTitle,      14, 1)

        self.type.currentIndexChanged.connect(
            self.on_type_change,
        )
 
    def getInfo( self ):
        """
        Get dict of title information

        Return a dict containing text from the
        various metadata boxes.

        Returns:
            dict

        """

        self.log.debug( 'Getting title metadata from widget' )
        info = super().getInfo()
        info.update( 
            {
                'extra'      : self.extra.currentText(),
                'extraTitle' : self.extraTitle.text(),
            }
        )
        if not self.season.isHidden(): # If season LineEdit hidden, then is movie
            info.update(
                {
                    'season'       : self.season.text(),
                    'episode'      : self.episode.text(),
                    'episodeTitle' : self.episodeTitle.text(),
                }
            )

        return info

    def setInfo( self, info ):
        """
        Set information in entry boxes for given title

        This updates the information in entry boxes
        to match that associated with each title on 
        the disc.

        Arguments:
            info (dict) : Information returned by a previous
                call to self.getInfo()

        Returns:
            None.

        """

        self.log.debug( 'setting title metadata for widget' )
        super().setInfo( info )
        self.season.setText(       info.get('season',       '' ) )
        self.episode.setText(      info.get('episode',      '' ) )
        self.episodeTitle.setText( info.get('episodeTitle', '' ) )
        self.extraTitle.setText(   info.get('extraTitle',   '' ) )
        extra = info.get('extra','')
        if extra == '':
            self.extra.setCurrentIndex( 0 )
        else:
            self.extra.setCurrentText( extra )
        
    def initSeriesWidget( self, label, placeholder ):
        """
        Helper method to create entries for series

        Arguments:
            label (str) : Label for the entry box
            placeholder (str) : Placeholder text for
                the entry box

        Returns:
            tuple : Reference to entry box label and
                entry box

        """

        label    = QtWidgets.QLabel(label)
        lineEdit = QtWidgets.QLineEdit()
        lineEdit.setPlaceholderText( placeholder )

        label.setHidden(    True )
        lineEdit.setHidden( True )

        return label, lineEdit

    def toggle_series_info_hidden(self, hidden):
        """
        Toggle various elements of widget

        Movie and Series objects have different
        metadata attributes avaiable. Toggles
        various entry boxes so that only those
        applicable to movie/series are shown

        Arguments:
            hidden (bool) : If True, then series
                info is hidden and vice versa

        Returns:
            None.

        """

        self.season.setHidden(            hidden )
        self.seasonLabel.setHidden(       hidden )
        self.episode.setHidden(           hidden )
        self.episodeLabel.setHidden(      hidden )
        self.episodeTitle.setHidden(      hidden )
        self.episodeTitleLabel.setHidden( hidden )
        self.extraTitleLabel.setHidden(   not hidden )
        self.extraTitle.setHidden(        not hidden )

    def on_type_change(self, index):

        text = CONTENTTYPES[index]
        self.extra.clear()
        if text == 'Movie':
            self.toggle_series_info_hidden( True )
            self.extra.addItems( MOVIETYPES )
        elif text == 'Series':
            self.toggle_series_info_hidden( False )
            self.extra.addItems( SERIESTYPES )
        else:
            return

        self.extra.addItems( EXTRATYPES )
            
#class MainWidget(QtWidgets.QMainWindow):
class MainWidget(QtWidgets.QDialog):

    default_title = 'Title'

    def __init__(self, discDev, *args, debug=False, dbdir=None, **kwargs ):

        super().__init__(*args, **kwargs)

        self.log = logging.getLogger( __name__ )
        self.curTitle  = None
        self.info      = None
        self.sizes     = None
        self.discDev   = discDev
        self.discID    = getDiscID( discDev )
        self.dbdir     = dbdir or DBDIR
        self.discLabel = None

        self.setWindowTitle()

        self.titleTree = QtWidgets.QTreeWidget()
        self.titleTree.setHeaderLabels( ['Type', 'Description'] )
        self.titleTree.setColumnWidth( 0, 100 )

        self.infoBox  = QtWidgets.QTextEdit()
        self.msgs     = QtWidgets.QTextEdit()
        self.save_but = QtWidgets.QPushButton( 'Save && Eject' )
        self.rip_but  = QtWidgets.QPushButton( 'Save && Rip' )
        self.save_but.clicked.connect( self.save )
        self.save_but.setEnabled( False )

        self.rip_but.clicked.connect(
            lambda *args, **kwargs : self.save(*args, rip=True, **kwargs)
        )
        self.rip_but.setEnabled( False )

        self.msgs.setReadOnly(True)

        self.discMetadata  = DiscMetadata()
        self.titleMetadata = TitleMetadata()
        self.titleMetadata.connect_parent( self.discMetadata )

        #self.discMetadata.isMovie.toggled.connect(
        #    self.titleMetadata.on_isMovie_change
        #)
        #self.discMetadata.isSeries.toggled.connect(
        #    self.titleMetadata.on_isSeries_change
        #)

        layout = QtWidgets.QGridLayout()
        layout.setColumnStretch(0, 3)
        layout.setColumnStretch(1, 2)
        layout.addWidget( self.discMetadata,  0, 0, 1, 2 ) 
        layout.addWidget( self.titleTree,     1, 0, 2, 1 )
        layout.addWidget( self.infoBox,       1, 1, 1, 1 )
        layout.addWidget( self.titleMetadata, 2, 1, 1, 1 )
        layout.addWidget( self.msgs,          3, 0, 1, 2 )
        layout.addWidget( self.save_but,      4, 0, 1, 2 )
        layout.addWidget( self.rip_but,       5, 0, 1, 2 )
        

        layout.setMenuBar(
            self._initMenu()
        )

        #central = QtWidgets.QWidget()
        #central.setLayout( layout )
        #self.setCentralWidget( central )
        self.setLayout(layout)
        self.resize( 720, 720 )

        self.loadDisc = MakeMKVInfo(discDev, debug=debug, dbdir=self.dbdir)
        self.loadDisc.signal.connect( self.msgs.append )
        self.loadDisc.finished.connect( self.buildTitleTree )
        self.loadDisc.start()

        self.show()

    def _initMenu(self):

        self.log.debug( 'Initializing menu' )
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

    def quit(self, *args, **kwargs):
        self.loadDisc.quit()
        self.accept()
        #self.reject()

    def setWindowTitle( self ):

        title = f"{self.discDev} [{self.discID}]"
        if self.discLabel:
            title = f"{title} - {self.discLabel}"
        super().setWindowTitle( title )

    def open( self, *args, **kwargs ):

        self.log.debug( 'Attempting to open disc JSON for editing' )
        dialog = QtWidgets.QFileDialog( directory=self.dbdir)
        dialog.setDefaultSuffix('json')
        dialog.setNameFilters( ['JSON (*.json)'] )
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return

        files = dialog.selectedFiles()
        if len(files) != 1:
            box = QtWidgets.QMessageBox( self )
            box.setText( 'Can only select one (1) file' )
            box.exec_()
            return

        self.msgs.clear()
        self.loadDisc.loadFile( json=files[0] )
        self.buildTitleTree( loadData( fpath=files[0] ) ) 

    def save( self, *args, **kwargs ):
        """
        Run when 'Save' button is clicked

        Loop over all items in the QTreeWidget.
        Any items that do NOT have default name,
        flag as actual titles to be ripped

        """

        self.log.debug( 'Saving data JSON' )

        info = self.discMetadata.getInfo()
        if info is None:
            self.log.debug( 'No disc metadata' )
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
            print(titleObj.makeMKVInfo)
            if titleObj.checkState(0) == 0:
                continue

            if not checkInfo(self, titleObj.info):
                return

            titles.update(
                {titleObj.titleID: titleObj.info},
            )
            sizes.update(
                {titleObj.titleID: int(titleObj.makeMKVInfo.get(SIZEKEY, '0'))},
            )

        if len(titles) == 0:
            self.log.info('No titles marked for ripping!')
            message = QtWidgets.QMessageBox()
            res = message.warning(
                self, 
                'No titles selected',
                'No titles have been selected for ripping. Please select some titles and try again',
            )
            return

        info['titles'] = titles

        message = QtWidgets.QMessageBox()
        res     = message.question(
                self, '', 'Are you sure the information is correct?',
                message.Yes | message.No
        )
        if res == message.Yes:
            saveData(info, discID=self.discID, replace=True, dbdir=self.dbdir)
            self.info = info if kwargs.get('rip', False) else 'skiprip'
            self.sizes = sizes
            self.accept()

    def selectTitle( self, obj, col ):
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

        self.infoBox.clear()                                        # Clear title/stream info box
        for key, val in obj.makeMKVInfo.items():                    # Iterate over makeMKVInfo for the title/stream
            self.infoBox.append( f"{key} : {val}" )                 # Format data and write to info box

        if not obj.isTitle: return                                  # If NOT title object

        if self.curTitle is not None:                               # If current title IS set
            self.curTitle.info.update(                              # Update the 'current' object with information from the titleMetadata pane
                self.titleMetadata.getInfo()
            )
        self.curTitle = obj                                         # Set curTitle title actual currently selected title
        for key, val in self.discMetadata.getInfo().items():
            if (val == ''):
                continue
            if (key not in obj.info) or (obj.info[key] == ''):
                obj.info[key] = val
             
        self.titleMetadata.setInfo( obj.info )                      # Update the titleMetadata pane with information from actual current title

    def buildTitleTree( self, info=None ):

        self.titleTree.clear()
        discInfo = self.loadDisc.discInfo
        titles = self.loadDisc.titles
        infoTitles = {}
        if info is not None:
            self.discID = info['discID']
            self.discMetadata.setInfo( info )
            infoTitles = info['titles']

        self.discLabel = discInfo.get('Name', None)
        self.setWindowTitle()

        # NOTE create nested data
        for titleID, titleInfo in titles.items():
            title = QtWidgets.QTreeWidgetItem( self.titleTree )
            title.setCheckState(0, 0 )
            title.makeMKVInfo = titleInfo
            title.isTitle     = True
            title.titleID     = titleID
            if titleID in infoTitles:
                title.info = infoTitles[titleID]
                title.setCheckState(0, 2)
            else:
                keys = ['Source Title Id', 'Source FileName', 'Segments Map']
                title.info = self.titleMetadata.getInfo()
                title.info.update(
                    {key : titleInfo.get(key, '') for key in keys}
                )
                    
            # Used to update old files to contain the Segments Map
            #if 'Segments Map' not in title.info:
            #    title.info['Segments Map'] = titleInfo['Segments Map']
            title.setText( 0, self.default_title)
            title.setText( 1, titleInfo['Tree Info'] )

            title.setFlags( title.flags() | QtCore.Qt.ItemIsUserCheckable )

            for streamID, streamInfo in titleInfo.pop('streams').items():
                child = QtWidgets.QTreeWidgetItem(title)
                child.makeMKVInfo = streamInfo
                child.isTitle     = False
                child.info        = {}
                child.setText( 0, streamInfo['Type'] )
                child.setText( 1, streamInfo['Tree Info'] )

        self.titleTree.currentItemChanged.connect( self.selectTitle )           # Run given method one object in QTreeWidget is clicked
        self.save_but.setEnabled( True )  # Enable 'Apply' Button after the tree is populated
        self.rip_but.setEnabled( True )  # Enable 'Apply' Button after the tree is populated


class ExistingDiscOptions(QtWidgets.QDialog):
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

    def __init__(self, parent=None, timeout=30):
        super().__init__(parent)
        
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

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(
            QtWidgets.QLabel(message)
        )
        layout.addWidget(self.timeout_label)
        layout.addWidget(self.button_box)

        self.setLayout(layout)

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
        self.done(SAVE)

    def action(self, button):
        self._timer.stop()
        if button == self.button_box.button(QtWidgets.QDialogButtonBox.Save):
            self.done(SAVE)
            return
        if button == self.button_box.button(QtWidgets.QDialogButtonBox.Open):
            self.done(OPEN)
            return
        self.done(IGNORE)
