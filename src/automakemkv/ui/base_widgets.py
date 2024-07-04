"""
Base widgets for metadata

"""

import logging

from PyQt5 import QtWidgets

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

MOVIETYPES = ['edition']
SERIESTYPES = ['']
CONTENTTYPES = ['', 'Movie', 'Series']
MEDIATYPES = [
    'DVD',
    'Blu-Ray',
    '4K Blu-Ray (UHD)',
]


class BaseMetadata(QtWidgets.QWidget):
    """
    Widget for disc metadata

    This widget is for entering metadata that
    pertains to the entire disc such as
    Movie/Series name, database IDs
    (e.g. TMDb, TVDb, IMDb), and release/
    first aired year.

    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.log = logging.getLogger(__name__)
        layout = QtWidgets.QGridLayout()

        self.title = QtWidgets.QLineEdit()
        self.year = QtWidgets.QLineEdit()
        self.tmdb = QtWidgets.QLineEdit()
        self.tvdb = QtWidgets.QLineEdit()
        self.imdb = QtWidgets.QLineEdit()

        self.type = QtWidgets.QComboBox()
        self.type.addItems(CONTENTTYPES)

        self.title.setPlaceholderText('Movie/Series Title')
        self.year.setPlaceholderText('Movie Released / Series First Aired')
        self.tmdb.setPlaceholderText('TheMovieDb ID')
        self.tvdb.setPlaceholderText('TheTVDb ID')
        self.imdb.setPlaceholderText('IMDb ID')

        layout.addWidget(self.title, 0, 0)
        layout.addWidget(self.year, 1, 0)

        # Build wiget for the type of video (Movie/TV)
        _layout = QtWidgets.QHBoxLayout()
        _layout.addWidget(QtWidgets.QLabel('Type : '))
        _layout.addWidget(self.type)
        video_type = QtWidgets.QWidget()
        video_type.setLayout(_layout)

        layout.addWidget(video_type, 2, 0)

        layout.addWidget(self.tmdb, 0, 1)
        layout.addWidget(self.tvdb, 1, 1)
        layout.addWidget(self.imdb, 2, 1)

        self.setLayout(layout)

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

        parent.title.textChanged.connect(self.title.setText)
        parent.year.textChanged.connect(self.year.setText)
        parent.tmdb.textChanged.connect(self.tmdb.setText)
        parent.tvdb.textChanged.connect(self.tvdb.setText)
        parent.imdb.textChanged.connect(self.imdb.setText)
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

        self.log.debug('Getting base metadata from widget')
        return {
            'title': self.title.text(),
            'year': self.year.text(),
            'tmdb': self.tmdb.text(),
            'tvdb': self.tvdb.text(),
            'imdb': self.imdb.text(),
            'isMovie': self.isMovie(),
            'isSeries': self.isSeries(),
        }

    def setInfo(self, info):

        self.log.debug('Setting disc metadata for widget')
        self.title.setText(
            info.get('title', '')
        )
        self.year.setText(
            info.get('year', '')
        )
        self.tmdb.setText(
            info.get('tmdb', '')
        )
        self.tvdb.setText(
            info.get('tvdb', '')
        )
        self.imdb.setText(
            info.get('imdb',  '')
        )

        if info.get('isMovie', False):
            self.type.setCurrentText('Movie')
        elif info.get('isSeries', False):
            self.type.setCurrentText('Series')


class DiscMetadata(BaseMetadata):
    """
    Widget for disc metadata

    This widget is for entering metadata that
    pertains to the entire disc such as
    Movie/Series name, database IDs
    (e.g. TMDb, TVDb, IMDb), and release/
    first aired year.

    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.log = logging.getLogger(__name__)

        layout = self.layout()
        self.upc = QtWidgets.QLineEdit()
        self.upc.setPlaceholderText('Universal Product Code')

        # Build wiget for the type of media (DVD/BluRay/etc.)
        self.media_type = QtWidgets.QComboBox()
        self.media_type.addItems([''] + MEDIATYPES)

        _layout = QtWidgets.QGridLayout()
        _layout.addWidget(QtWidgets.QLabel('Media : '), 0, 0)
        _layout.addWidget(self.media_type, 0, 1)
        media_type = QtWidgets.QWidget()
        media_type.setLayout(_layout)

        layout.addWidget(media_type, 3, 0)
        layout.addWidget(self.upc, 3, 1)

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

        self.log.debug('Getting disc metadata from widget')
        info = super().getInfo()
        info['media_type'] = self.media_type.currentText()
        info['upc'] = self.upc.text()
        print(info)
        return info

    def setInfo(self, info):

        self.log.debug('Setting disc metadata fro widget')
        super().setInfo(info)
        self.upc.setText(
            info.get('upc', '')
        )
        self.media_type.setCurrentText(
            info.get('media_type', '')
        )


class TitleMetadata(BaseMetadata):
    """
    Widget for metadata about a title

    This widget is designed to collect
    metadata for individual titles on the
    disc.

    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.log = logging.getLogger(__name__)
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

        layout.addWidget(self.seasonLabel, 10, 0)
        layout.addWidget(self.season, 10, 1)
        layout.addWidget(self.episodeLabel, 11, 0)
        layout.addWidget(self.episode, 11, 1)
        layout.addWidget(self.episodeTitleLabel, 12, 0)
        layout.addWidget(self.episodeTitle, 12, 1)

        self.extraLabel = QtWidgets.QLabel('Extra')
        self.extra = QtWidgets.QComboBox()

        self.extraTitleLabel = QtWidgets.QLabel('Extra Title')
        self.extraTitle = QtWidgets.QLineEdit()
        self.extraTitle.setPlaceholderText(
            "Label for 'Extra' type"
        )

        self.extraTitleLabel.setHidden(True)
        self.extraTitle.setHidden(True)

        layout.addWidget(self.extraLabel, 13, 0)
        layout.addWidget(self.extra, 13, 1)
        layout.addWidget(self.extraTitleLabel, 14, 0)
        layout.addWidget(self.extraTitle, 14, 1)

        self.type.currentIndexChanged.connect(
            self.on_type_change,
        )

    def getInfo(self):
        """
        Get dict of title information

        Return a dict containing text from the
        various metadata boxes.

        Returns:
            dict

        """

        self.log.debug('Getting title metadata from widget')
        info = super().getInfo()
        info.update(
            {
                'extra': self.extra.currentText(),
                'extraTitle': self.extraTitle.text(),
            }
        )
        # If season LineEdit hidden, then is movie
        if not self.season.isHidden():
            info.update(
                {
                    'season': self.season.text(),
                    'episode': self.episode.text(),
                    'episodeTitle': self.episodeTitle.text(),
                }
            )

        return info

    def setInfo(self, info):
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

        self.log.debug('setting title metadata for widget')
        super().setInfo(info)
        self.season.setText(info.get('season', ''))
        self.episode.setText(info.get('episode', ''))
        self.episodeTitle.setText(info.get('episodeTitle', ''))
        self.extraTitle.setText(info.get('extraTitle', ''))
        extra = info.get('extra', '')
        if extra == '':
            self.extra.setCurrentIndex(0)
        else:
            self.extra.setCurrentText(extra)

    def initSeriesWidget(self, label, placeholder):
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

        label = QtWidgets.QLabel(label)
        lineEdit = QtWidgets.QLineEdit()
        lineEdit.setPlaceholderText(placeholder)

        label.setHidden(True)
        lineEdit.setHidden(True)

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

        self.season.setHidden(hidden)
        self.seasonLabel.setHidden(hidden)
        self.episode.setHidden(hidden)
        self.episodeLabel.setHidden(hidden)
        self.episodeTitle.setHidden(hidden)
        self.episodeTitleLabel.setHidden(hidden)
        self.extraTitleLabel.setHidden(not hidden)
        self.extraTitle.setHidden(not hidden)

    def on_type_change(self, index):

        text = CONTENTTYPES[index]
        self.extra.clear()
        if text == 'Movie':
            self.toggle_series_info_hidden(True)
            self.extra.addItems(MOVIETYPES)
        elif text == 'Series':
            self.toggle_series_info_hidden(False)
            self.extra.addItems(SERIESTYPES)
        else:
            return

        self.extra.addItems(EXTRATYPES)
