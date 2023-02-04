from PyQt5 import QtCore, QtWidgets, QtGui, Qt

from . import parseMakeMKV

def buildFiles( info ):

    if info['tmdb'] != '':
        key = info['tmdb']
        if not key.startswith('tmdb'):
            key = f"tmdb{key}"
    elif info['tvdb'] != '':
        key = info['tvdb']
        if not key.startswith('tvdb'):
            key = f"tvdb{key}"
    else:
        raise Exception( 'Must enter either TMDb or TVDb' )

    files = {}
    for title in info['titles']:
        files[title[1]] = f"{key}.{title[0]}.mkv"

    return files

class MediaIDs( QtWidgets.QWidget ):

    def __init__(self, *args, **kwargs ):
        super().__init__(*args, **kwargs)

        layout = QtWidgets.QGridLayout()
        layout.addWidget(
            QtWidgets.QLabel( 'TheMovieDB ID' ),
            0, 0
        )
        layout.addWidget(
            QtWidgets.QLabel( 'TheTVDB ID' ),
            1, 0
        )
        layout.addWidget(
            QtWidgets.QLabel( 'IMDb ID' ),
            2, 0
        )

        self.tmdb = QtWidgets.QLineEdit()
        self.tvdb = QtWidgets.QLineEdit()
        self.imdb = QtWidgets.QLineEdit()

        layout.addWidget( self.tmdb, 0, 1 )
        layout.addWidget( self.tvdb, 1, 1 )
        layout.addWidget( self.imdb, 2, 1 )

        self.setLayout( layout )

        self.show()

    def getDict(self):

        return {
            'tmdb' : self.tmdb.text(),
            'tvdb' : self.tvdb.text(),
            'imdb' : self.imdb.text(),
        }

class MainWidget( QtWidgets.QMainWindow ):

    default_title = 'Default Title'

    def __init__(self, *args, **kwargs ):

        super().__init__(*args, **kwargs)

        self.titles  = None
        self.streams = None
        self.tree    = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels( ['Type', 'Description'] )

        self.info   = QtWidgets.QTextEdit()
        self.msgs   = QtWidgets.QTextEdit()
        self.button = QtWidgets.QPushButton( 'Apply' )
        self.button.clicked.connect( self.apply )
        self.button.setEnabled( False )
        self.msgs.setReadOnly(True)

        self.mediaIDs = MediaIDs()
        layout = QtWidgets.QGridLayout()
        layout.addWidget( self.mediaIDs, 0, 0, 1, 2 ) 
        layout.addWidget( self.tree,     1, 0, 1, 1 )
        layout.addWidget( self.info,     1, 1, 1, 1 )
        layout.addWidget( self.msgs,     2, 0, 1, 2 )
        layout.addWidget( self.button,   3, 0, 1, 2 )

        central = QtWidgets.QWidget()
        central.setLayout( layout )
        self.setCentralWidget( central )
        
        self.titlesThread = parseMakeMKV.MakeMKVParser()
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

        info   = self.mediaIDs.getDict()
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

        info['titles'] = titles
        files = buildFiles( info )
        print( files )

    def updateInfo(self, info):
        self.info.clear()
        for key, val in info.items():
            self.info.append(
                f"{key} : {val}"
            )

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
            self.updateInfo( self.titles[ title ] )
        elif title in self.streams:
            self.updateInfo( self.streams[ title ] )

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

            title.setFlags( title.flags() | QtCore.Qt.ItemIsEditable )

            for streamID, streamInfo in titleInfo.pop('streams').items():
                child = QtWidgets.QTreeWidgetItem(title)
                child.setText( 0, streamInfo['Type'] )
                child.setText( 1, streamInfo['Tree Info'] )
                self.streams[ str(child) ] = streamInfo 

        self.tree.currentItemChanged.connect( self.selectTitle )           # Run given method one object in QTreeWidget is clicked
        self.button.setEnabled( True )  # Enable 'Apply' Button after the tree is populated
