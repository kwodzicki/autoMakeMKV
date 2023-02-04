import logging
import os

LOG    = logging.getLogger( __name__ )

APPDIR = os.path.dirname( os.path.abspath( __file__ ) )
DBDIR  = os.path.join( os.path.expanduser('~'), f".{__name__}DB" )
TEST_DATA_FILE = os.path.join(
    APPDIR, 'testing.txt'
)

os.makedirs( DBDIR, exist_ok=True )
