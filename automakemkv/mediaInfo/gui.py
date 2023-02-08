import os

from PyQt5 import QtCore, QtWidgets, QtGui, Qt

from ..makemkv import MakeMKVParser, MakeMKVThread
from .utils import DBDIR, checkInfo, getDiscID, loadData, saveData

EXTRATYPES = [ 
    'behindthescenes', 'deleted', 'featurette',
    'interview', 'scene', 'short', 'trailer', 'other',
]

MOVIETYPES  = ['edition']
SERIESTYPES = ['']

def main( discDev='/dev/sr0', **kwargs ):

    app = QtWidgets.QApplication(['MakeMKV MediaID'])
    mediaIDs = MainWidget( discDev, **kwargs )
    app.exec_()

    return mediaIDs.info

class DiscMetadata( QtWidgets.QWidget ):
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

        layout = QtWidgets.QGridLayout()

        layout.addWidget( QtWidgets.QLabel( 'Title' ),         0, 0 )
        layout.addWidget( QtWidgets.QLabel( 'Year' ),          1, 0 )

        layout.addWidget( QtWidgets.QLabel( 'TheMovieDB ID' ), 0, 2 )
        layout.addWidget( QtWidgets.QLabel( 'TheTVDB ID' ),    1, 2 )
        layout.addWidget( QtWidgets.QLabel( 'IMDb ID' ),       2, 2 )
        layout.addWidget( QtWidgets.QLabel( 'UPC' ),           3, 2 )

        self.title    = QtWidgets.QLineEdit()
        self.year     = QtWidgets.QLineEdit()
        self.tmdb     = QtWidgets.QLineEdit()
        self.tvdb     = QtWidgets.QLineEdit()
        self.imdb     = QtWidgets.QLineEdit()
        self.upc      = QtWidgets.QLineEdit()

        self.isMovie  = QtWidgets.QRadioButton( 'Movie' )
        self.isSeries = QtWidgets.QRadioButton( 'Series' )

        self.title.setPlaceholderText( 'Movie/Series Title' )
        self.year.setPlaceholderText(  'Movie Released / Series First Aired' )
        self.tmdb.setPlaceholderText(  'Movie/Series ID' )
        self.tvdb.setPlaceholderText(  'Movie/Series ID' )
        self.imdb.setPlaceholderText(  'Movie/Series ID' )
        self.upc.setPlaceholderText(   'Universal Product Code' )

        layout.addWidget( self.title,    0, 1 )
        layout.addWidget( self.year,     1, 1 )

        layout.addWidget( self.isMovie,  2, 0 )
        layout.addWidget( self.isSeries, 2, 1 )
        layout.addWidget( self.tmdb,     0, 3 )
        layout.addWidget( self.tvdb,     1, 3 )
        layout.addWidget( self.imdb,     2, 3 )
        layout.addWidget( self.upc,      3, 3 )

        self.setLayout( layout )

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

        info = {
            'title'    : self.title.text(),
            'year'     : self.year.text(),
            'tmdb'     : self.tmdb.text(),
            'tvdb'     : self.tvdb.text(),
            'imdb'     : self.imdb.text(),
            'upc'      : self.upc.text(),
            'isMovie'  : self.isMovie.isChecked(),
            'isSeries' : self.isSeries.isChecked(),
        }

        if checkInfo( self, info ):
            return info
        return None

    def setInfo(self, info):

        self.title.setText( info.get('title', '') )
        self.year.setText(  info.get('year',  '') ) 
        self.tmdb.setText(  info.get('tmdb',  '') ) 
        self.tvdb.setText(  info.get('tvdb',  '') ) 
        self.imdb.setText(  info.get('imdb',  '') )
        self.upc.setText(   info.get('upc',   '') )

        if info.get('isMovie', False):
            self.isMovie.setChecked(True)
        elif info.get('isSeries', False):
            self.isSeries.setChecked(True)

class TitleMetadata( QtWidgets.QWidget ):
    """
    Widget for metadata about a title

    This widget is designed to collect
    metadata for individual titles on the
    disc.

    """

    def __init__(self, *args, **kwargs ):
        super().__init__(*args, **kwargs)

        layout = QtWidgets.QGridLayout()

        self.seasonLabel, self.season = (
            self.initSeriesWidget('Season', 'Season number')
        )
        self.episodeLabel, self.episode = (
            self.initSeriesWidget('Episode', 'Episode number')
        )
        self.episodeTitleLabel, self.episodeTitle = (
            self.initSeriesWidget('Title', 'Episode Title')
        )

        layout.addWidget( self.seasonLabel,       0, 0 )
        layout.addWidget( self.season,            0, 1 )
        layout.addWidget( self.episodeLabel,      1, 0 )
        layout.addWidget( self.episode,           1, 1 )
        layout.addWidget( self.episodeTitleLabel, 2, 0 )
        layout.addWidget( self.episodeTitle,      2, 1 )

        self.extraLabel = QtWidgets.QLabel('Extra')
        self.extra      = QtWidgets.QComboBox()

        self.extraTitleLabel = QtWidgets.QLabel('Extra Title')
        self.extraTitle      = QtWidgets.QLineEdit()
        self.extraTitle.setPlaceholderText(
            "Label for 'Extra' type"
        )

        self.extraTitleLabel.setHidden( True )
        self.extraTitle.setHidden( True )

        layout.addWidget( self.extraLabel,      3, 0)
        layout.addWidget( self.extra,           3, 1)
        layout.addWidget( self.extraTitleLabel, 4, 0)
        layout.addWidget( self.extraTitle,      4, 1)

        self.setLayout( layout )

    def getInfo( self ):
        """
        Get dict of title information

        Return a dict containing text from the
        various metadata boxes.

        Returns:
            dict

        """

        info = {
            'extra'      : self.extra.currentText(),
            'extraTitle' : self.extraTitle.text(),
        }
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

    def on_isMovie_change(self, selected):
        """
        Change title info dialog to movie attributes

        Intended to be connect to the DiscMetadata
        object's isMovie radio button so that when
        a Movie is selected, the title attriubtes
        for a movie are displayed

        Arguments:
            selected (bool) : Selected state of
                the radio button

        """

        if not selected: return

        self.toggle_series_info_hidden( True )
        self.extra.clear()
        self.extra.addItems( MOVIETYPES + EXTRATYPES )

    def on_isSeries_change(self, selected):
        """
        Change title info dialog to series attributes

        Intended to be connect to the DiscMetadata
        object's isSeries radio button so that when
        a Series is selected, the title attriubtes
        for a series are displayed

        Arguments:
            selected (bool) : Selected state of
                the radio button

        """

        if not selected: return

        self.toggle_series_info_hidden( False )
        self.extra.clear()
        self.extra.addItems( SERIESTYPES + EXTRATYPES )
        
class MainWidget( QtWidgets.QMainWindow ):

    default_title = 'Title'

    def __init__(self, discDev, *args, debug=False, **kwargs ):

        super().__init__(*args, **kwargs)

        self._initMenu()
        self.curTitle  = None
        self.info      = None
        self.discID    = getDiscID( discDev )

        self.titleTree = QtWidgets.QTreeWidget()
        self.titleTree.setHeaderLabels( ['Type', 'Description'] )
        self.titleTree.setColumnWidth( 0, 150 )

        self.infoBox = QtWidgets.QTextEdit()
        self.msgs    = QtWidgets.QTextEdit()
        self.button  = QtWidgets.QPushButton( 'Save' )
        self.button.clicked.connect( self.save )
        self.button.setEnabled( False )
        self.msgs.setReadOnly(True)

        self.discMetadata  = DiscMetadata()
        self.titleMetadata = TitleMetadata()
        self.discMetadata.isMovie.toggled.connect(
            self.titleMetadata.on_isMovie_change
        )
        self.discMetadata.isSeries.toggled.connect(
            self.titleMetadata.on_isSeries_change
        )

        layout = QtWidgets.QGridLayout()
        layout.setColumnStretch(0, 3)
        layout.setColumnStretch(1, 2)
        layout.addWidget( self.discMetadata,  0, 0, 1, 2 ) 
        layout.addWidget( self.titleTree,     1, 0, 2, 1 )
        layout.addWidget( self.infoBox,       1, 1, 1, 1 )
        layout.addWidget( self.titleMetadata, 2, 1, 1, 1 )
        layout.addWidget( self.msgs,          3, 0, 1, 2 )
        layout.addWidget( self.button,        4, 0, 1, 2 )

        central = QtWidgets.QWidget()
        central.setLayout( layout )
        self.setCentralWidget( central )
        self.resize( 720, 720 )

        self.titlesThread = MakeMKVThread( discDev, debug=debug )
        self.titlesThread.str_signal.connect( self.msgs.append )
        self.titlesThread.finished.connect( self.buildTitleTree )
        self.titlesThread.start()

        self.show()

    def _initMenu(self):

        menuBar    = self.menuBar()

        fileMenu   = menuBar.addMenu("File")
        actionOpen = QtWidgets.QAction("&Open...", self)
        actionOpen.triggered.connect( self.open )
        fileMenu.addAction( actionOpen )

        actionSave = QtWidgets.QAction("&Save", self)
        actionSave.triggered.connect( self.save )
        fileMenu.addAction(actionSave)
        fileMenu.addSeparator()
        fileMenu.addAction("Quit")

    def open( self, *args, **kwargs ):

        dialog = QtWidgets.QFileDialog( directory=DBDIR )
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

        self.titlesThread.loadFile( json=files[0] )
        self.buildTitleTree( loadData( fpath=files[0] ) ) 

    def save( self, *args, **kwargs ):
        """
        Run when 'Save' button is clicked

        Loop over all items in the QTreeWidget.
        Any items that do NOT have default name,
        flag as actual titles to be ripped

        """

        info = self.discMetadata.getInfo()
        if info is None: return 

        if self.curTitle is not None:
            self.curTitle.info.update(
                self.titleMetadata.getInfo()
            )

        titles = {}
        root   = self.titleTree.invisibleRootItem()
        for i in range( root.childCount() ):
            titleObj   = root.child( i )          # Get the object from the QTreeWidget
            if titleObj.checkState(0) == 0:
                continue

            titles.update( { titleObj.titleID : titleObj.info } )

        if len(titles) == 0:
            print('No titles marked for ripping!')
            return

        info['titles'] = titles

        confirm = QtWidgets.QMessageBox()
        res     = confirm.question(
                self, '', 'Are you sure the information is correct?',
                confirm.Yes | confirm.No
        )
        if res == confirm.Yes:
            saveData(info, discID=self.discID, replace=True)
            self.info = info
            self.close()

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
        self.titleMetadata.setInfo( obj.info )                      # Update the titleMetadata pane with information from actual current title


    def buildTitleTree( self, info=None ):

        self.titleTree.clear()
        titles = self.titlesThread.titles
        infoTitles = {}
        if info is not None:
            self.discID = info['discID']
            self.discMetadata.setInfo( info )
            infoTitles = info['titles']

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
                title.info = {'Source Title Id' : titleInfo['Source Title Id']}
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
        self.button.setEnabled( True )  # Enable 'Apply' Button after the tree is populated
