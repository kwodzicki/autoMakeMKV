import sys
from PyQt5.QtWidgets import QApplication

from mediaID.gui import MainWidget

if __name__ == '__main__':
    app = QApplication(sys.argv)
    main = MainWidget()

    sys.exit( app.exec_() )
