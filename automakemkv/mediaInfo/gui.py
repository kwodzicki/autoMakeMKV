from PyQt5 import QtCore, QtWidgets, QtGui, Qt

from ..makemkv import MakeMKVParser
from .utils import checkInfo

TYPES = [
    'edition', 'behindthescenes', 'deleted', 'featurette',
    'interview', 'scene', 'short', 'trailer', 'other',
]

def main( discDev='/dev/sr0', **kwargs ):

    app = QtWidgets.QApplication(['MakeMKV MediaID'])
    mediaIDs = MainWidget( discDev, **kwargs )
    app.exec_()

    return mediaIDs.info

class DiscMetadata( QtWidgets.QWidget ):

    def __init__(self, *args, **kwargs ):
        super().__init__(*args, **kwargs)

        layout = QtWidgets.QGridLayout()
        layout.addWidget(
            QtWidgets.QLabel( 'Title' ),
            0, 0
        )
        layout.addWidget(
            QtWidgets.QLabel( 'Year' ),
            1, 0
        )

        layout.addWidget(
            QtWidgets.QLabel( 'TheMovieDB ID' ),
            0, 2
        )
        layout.addWidget(
            QtWidgets.QLabel( 'TheTVDB ID' ),
            1, 2
        )
        layout.addWidget(
            QtWidgets.QLabel( 'IMDb ID' ),
            2, 2
        )

        self.title    = QtWidgets.QLineEdit()
        self.year     = QtWidgets.QLineEdit()
        self.tmdb     = QtWidgets.QLineEdit()
        self.tvdb     = QtWidgets.QLineEdit()
        self.imdb     = QtWidgets.QLineEdit()

        self.isMovie  = QtWidgets.QRadioButton( 'Movie' )
        self.isSeries = QtWidgets.QRadioButton( 'Series' )


        self.title.setPlaceholderText( 'Movie/Series Title' )
        self.year.setPlaceholderText(  'Movie/Series Release/First Aired' )
        self.tmdb.setPlaceholderText(  'Movie/Series ID' )
        self.tvdb.setPlaceholderText(  'Movie/Series ID' )
        self.imdb.setPlaceholderText(  'Movie/Series ID' )

        layout.addWidget( self.title,    0, 1 )
        layout.addWidget( self.year,     1, 1 )
        layout.addWidget( self.isMovie,  2, 0 )
        layout.addWidget( self.isSeries, 2, 1 )
        layout.addWidget( self.tmdb,     0, 3 )
        layout.addWidget( self.tvdb,     1, 3 )
        layout.addWidget( self.imdb,     2, 3 )

        self.setLayout( layout )

        self.show()

    def getDict(self):

        info = {
            'title'    : self.title.text(),
            'year'     : self.year.text(),
            'tmdb'     : self.tmdb.text(),
            'tvdb'     : self.tvdb.text(),
            'imdb'     : self.imdb.text(),
            'isMovie'  : self.isMovie.isChecked(),
            'isSeries' : self.isSeries.isChecked(),
        }

        if checkInfo( self, info ):
            return info
        return None

class TitleMetadata( QtWidgets.QWidget ):

    def __init__(self, *args, **kwargs ):
        super().__init__(*args, **kwargs)

        layout = QtWidgets.QGridLayout()
        layout.addWidget(
            QtWidgets.QLabel('Title'), 0, 0
        )
        layout.addWidget(
            QtWidgets.QLabel('Type'), 3, 0
        )

        self.title   = QtWidgets.QLineEdit()
        self.type    = QtWidgets.QComboBox()
        self.type.addItems( TYPES )

        layout.addWidget( self.title, 0, 1)
        layout.addWidget( self.type,  3, 1)

        self.setLayout( layout )
    
        
class MainWidget( QtWidgets.QMainWindow ):

    default_title = 'Title'

    def __init__(self, discDev, *args, debug=False, **kwargs ):

        super().__init__(*args, **kwargs)

        self.titles  = None
        self.streams = None
        self.info    = None

        self.tree    = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels( ['Type', 'Description'] )
        self.tree.setColumnWidth( 0, 150 )

        self.info    = QtWidgets.QTextEdit()
        self.msgs    = QtWidgets.QTextEdit()
        self.button  = QtWidgets.QPushButton( 'Apply' )
        self.button.clicked.connect( self.apply )
        self.button.setEnabled( False )
        self.msgs.setReadOnly(True)

        self.titleMetadata = TitleMetadata()

        self.discMetadata = DiscMetadata()
        layout = QtWidgets.QGridLayout()
        layout.setColumnStretch(0, 3)
        layout.setColumnStretch(1, 2)
        layout.addWidget( self.discMetadata,  0, 0, 1, 2 ) 
        layout.addWidget( self.tree,          1, 0, 2, 1 )
        layout.addWidget( self.info,          1, 1, 1, 1 )
        layout.addWidget( self.titleMetadata, 2, 1, 1, 1 )
        layout.addWidget( self.msgs,          3, 0, 1, 2 )
        layout.addWidget( self.button,        4, 0, 1, 2 )

        central = QtWidgets.QWidget()
        central.setLayout( layout )
        self.setCentralWidget( central )
        self.resize( 720, 720 )

        self.titlesThread = MakeMKVParser( discDev, debug=debug )
        self.titlesThread.str_signal.connect( self.msgs.append )
        self.titlesThread.finished.connect( self.buildTitleTree )
        self.titlesThread.start()

        self.show()
    
    def apply( self, *args, **kwargs ):
        """
        Run when 'Apply' button is clicked

        Loop over all items in the QTreeWidget.
        Any items that do NOT have default name,
        flag as actual titles to be ripped

        """

        info = self.discMetadata.getDict()

        titles = []
        root   = self.tree.invisibleRootItem()
        keys   = list( self.titles.keys() )       # Get keys from titles object; some have most likely changed, so need to index using order, not key
        for i in range( root.childCount() ):
            treeObj   = root.child( i )          # Get the object from the QTreeWidget
            title     = treeObj.text(0)         # Get name of title in the QTreeWidget object
            if self.default_title in title:     # If the default_title string is in the title from the QTreeWidget object
                continue                        # Skip it because it is not a 'real' title that needs to be ripped
            titleDict = self.titles[keys[i]]
            titles.append(
                (title, titleDict['Original Title Id'])
            )

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
            self.info = info
            self.close()

    def selectTitle( self, obj, col ):
        """
        Run when obj in Tree is selected

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

        title = str(obj)
        if title in self.titles:
            info = self.titles[ title ]
        elif title in self.streams:
            info = self.streams[ title ]
        else:
            return

        self.info.clear()
        for key, val in info.items():
            self.info.append(
                f"{key} : {val}"
            )

    def buildTitleTree( self ):

        titles = self.titlesThread.titles

        self.titles  = {}
        self.streams = {}
        # NOTE create nested data
        for titleID, titleInfo in titles.items():
            title = QtWidgets.QTreeWidgetItem( self.tree )
            self.titles[ str(title) ] = titleInfo

            title.setText( 0, f'{self.default_title} {titleID}')
            title.setText( 1, titleInfo['Tree Info'] )

            title.setFlags( title.flags() | QtCore.Qt.ItemIsUserCheckable )
            title.setCheckState(0, False )

            for streamID, streamInfo in titleInfo.pop('streams').items():
                child = QtWidgets.QTreeWidgetItem(title)
                child.setText( 0, streamInfo['Type'] )
                child.setText( 1, streamInfo['Tree Info'] )
                self.streams[ str(child) ] = streamInfo 

        self.tree.currentItemChanged.connect( self.selectTitle )           # Run given method one object in QTreeWidget is clicked
        self.button.setEnabled( True )  # Enable 'Apply' Button after the tree is populated
