from .. import STREAM
from .gui import DiscDialog


def cli():
    import sys
    import argparse
    from PyQt5.QtWidgets import QApplication

    parser = argparse.ArgumentParser()
    parser.add_argument(
        'discdev',
        type=str,
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Set to enable debugging mode',
    )
    parser.add_argument(
        '--loglevel',
        type=int,
        default=30,
        help='Set logging level',
    )

    args = parser.parse_args()
    STREAM.setLevel(args.loglevel)
    app = QApplication(sys.argv)
    DiscDialog(args.discdev)
    app.exec_()
