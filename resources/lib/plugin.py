# -*- coding: utf-8 -*-
"""
The plugin module

Copyright 2017-2018, Leo Moll and Dominik Schlösser
SPDX-License-Identifier: MIT
"""

# -- Imports ------------------------------------------------# from future import standard_library
# from builtins import *
# standard_library.install_aliases()
import os
import time
from datetime import datetime

# pylint: disable=import-error
import xbmcgui
import xbmcplugin

from resources.lib.kodi.kodiaddon import KodiPlugin

from resources.lib.storeMySql import StoreMySQL
from resources.lib.storeSqlite import StoreSQLite
from resources.lib.notifierKodi import NotifierKodi
from resources.lib.downloader import Downloader
from resources.lib.searches import RecentSearches
import resources.lib.ui.livestreamUi as LivestreamUi
import resources.lib.ui.channelUi as ChannelUi
import resources.lib.ui.showUi as ShowUi
import resources.lib.ui.letterUi as LetterUi
import resources.lib.ui.filmlistUi as FilmlistUi
import resources.lib.ui.seasonUi as SeasonUi
from resources.lib.ui.jump import Jump
import resources.lib.paging as Paging
import resources.lib.seasons as Seasons
import resources.lib.variants as Variants
from resources.lib.metadata import Metadata
from resources.lib.metadataPrefetch import MetadataPrefetch

import resources.lib.appContext as appContext

# -- Constants ----------------------------------------------
# Where the show's name sits in a row of the film query.
SHOWNAME = 2

# -- Classes ------------------------------------------------


class MediathekViewPlugin(KodiPlugin):
    """ The main plugin class """

    def __init__(self):
        super(MediathekViewPlugin, self).__init__()
        self.settings = appContext.MVSETTINGS
        self.notifier = appContext.MVNOTIFIER
        self.logger = appContext.MVLOGGER.get_new_logger('MediathekViewPlugin')
        if self.settings.getDatabaseType() == 0:
            self.logger.debug('Database driver: Internal (sqlite)')
            self.database = StoreSQLite()
        elif self.settings.getDatabaseType() == 1:
            self.logger.debug('Database driver: External (mysql)')
            self.database = StoreMySQL()
        else:
            self.logger.warn('Unknown Database driver selected')
            self.database = None
        self.metadata = Metadata()
        #
        # self.database = Store()

    def show_main_menu(self):
        """ Creates the main menu of the plugin """
        xbmcplugin.setContent(self.addon_handle, '')
        # Search
        self.add_folder_item(
            30902,
            {'mode': "search"},
            icon=os.path.join(self.path, 'resources', 'icons', 'search-m.png'),
            fanart=os.path.join(self.path, 'resources', 'icons', 'search-f.png')
        )
        # Browse livestreams
        self.add_folder_item(
            30903,
            {'mode': "livestreams"},
            icon=os.path.join(self.path, 'resources', 'icons', 'live2-m.png'),
            fanart=os.path.join(self.path, 'resources', 'icons', 'live2-f.png')
        )
        # Browse recently added by channel
        self.add_folder_item(
            30904,
            {'mode': "recentchannels"},
            icon=os.path.join(self.path, 'resources', 'icons', 'new-m.png'),
            fanart=os.path.join(self.path, 'resources', 'icons', 'new-f.png')
        )
        # Browse Shows (Channel > Show > Film | Channel > letter > show > Film)
        self.add_folder_item(
            30905,
            {'mode': "channels"},
            icon=os.path.join(self.path, 'resources', 'icons', 'movie-m.png'),
            fanart=os.path.join(self.path, 'resources', 'icons', 'movie-f.png')
        )
        # Database Information
        self.add_action_item(
            30908,
            {'mode': "action-dbinfo"},
            icon=os.path.join(self.path, 'resources', 'icons', 'dbinfo-m.png'),
            fanart=os.path.join(self.path, 'resources', 'icons', 'dbinfo-f.png')
        )
        # Manual database update
        if self.settings.getDatabaseUpateMode() == 1 or self.settings.getDatabaseUpateMode() == 2:
            self.add_action_item(
                30909,
                {'mode': "action-dbupdate"},
                icon=os.path.join(self.path, 'resources', 'icons', 'download-m.png'),
                fanart=os.path.join(self.path, 'resources', 'icons', 'download-f.png')
            )
        #
        self.end_of_directory()

    def run(self):
        """ Execution of the plugin """
        start = time.time()
        # save last activity timestamp
        self.settings.user_activity()
        # process operation
        self.logger.info("Plugin invoked with parameters {}", self.args)
        #
        mode = self.get_arg('mode', None)
        if mode is None:
            self.show_main_menu()
        elif mode == 'search':
            self.show_search_menu()
        elif mode == 'searchhistory':
            self.show_search_history()
        elif mode == 'newsearch':
            self.new_search()
        elif mode == 'research':
            search = self.get_arg('search', '')
            self._generateSearch(search)
            if self.get_arg('doNotSave', 'false') == 'false':
                RecentSearches(self).load().add(search).save()
            #
        elif mode == 'delsearch':
            search = self.get_arg('search', '')
            RecentSearches(self).load().delete(search).save().populate()
            self.run_builtin('Container.Refresh')
            #
        elif mode == 'livestreams':
            ui = LivestreamUi.LivestreamUi(self)
            ui.generate(self.database.getLivestreams())
            #
        elif mode == 'recent':
            channel = self.get_arg('channel', "")
            channel = "" if channel == "0" else channel
            self._generateFilms(
                lambda offset, limit: self.database.getRecentFilms(channel, offset, limit),
                {'mode': 'recent', 'channel': channel or '0'})
            # self.database.get_recents(channel, FilmUI(self))
            #
        elif mode == 'recentchannels':
            #
            self.add_folder_item(
                30906,
                {'mode': 'recent' },
                icon=os.path.join(self.path, 'resources', 'icons', 'broadcast-m.png'),
                fanart=os.path.join(self.path, 'resources', 'icons', 'broadcast-f.png')
            )
            ui = ChannelUi.ChannelUi(self, 'recent')
            ui.generate(self.database.getChannelsRecent())
        elif mode == 'channels':
            #
            self.add_folder_item(
                30906,
                {'mode': 'initial' },
                icon=os.path.join(self.path, 'resources', 'icons', 'broadcast-m.png'),
                fanart=os.path.join(self.path, 'resources', 'icons', 'broadcast-f.png')
            )
            #
            ui = ChannelUi.ChannelUi(self, 'shows')
            ui.generate(self.database.getChannels())
        elif mode == 'action-dbinfo':
            self.run_builtin("ActivateWindow(busydialognocancel)")
            self.show_db_info()
            self.run_builtin("Dialog.Close(busydialognocancel)")
        elif mode == 'refreshmetadata':
            # The only cure for a wrong match: forget this one show and ask
            # again. Without a library there is no dialog to pick artwork in.
            self.metadata.forget(self.get_arg('showname', ''))
            self.run_builtin('Container.Refresh')
        elif mode == 'gotoshow':
            self._gotoShow(self.get_arg('channel', ''), self.get_arg('show', ''),
                           self.get_arg('id', ''))
        elif mode == 'fetchmetadata':
            self._fetchMetadata()
        elif mode == 'discardmetadata':
            self.metadata.discardAll()
            self.notifier.show_notification(30996, 30997)
        elif mode == 'action-dbupdate':
            self.settings.set_update_triggered('true')
            self.notifier.show_notification(30963, 30964)
        elif mode == 'initial':
            ui = LetterUi.LetterUi(self)
            ui.generate(self.database.getStartLettersOfShows())
        elif mode == 'shows':
            channel = self.get_arg('channel', "")
            channel = "" if channel == "0" else channel
            initial = self.get_arg('initial', "")
            #initial = "" if initial == "0" else initial
            # self.database.get_shows(channel, initial, ShowUI(self))
            ui = ShowUi.ShowUi(self)
            if initial == "":
                ui.generate(self.database.getShowsByChannnel(channel), self.metadata)
            else:
                ui.generate(self.database.getShowsByLetter(initial), self.metadata)
        elif mode == 'films':
            show = self.get_arg('show', "")
            show = "" if show == "0" else show
            channel = self.get_arg('channel', "")
            channel = "" if channel == "0" else channel
            season = self.get_arg('season', "")
            films = self._withoutDuplicates(self.database.getFilms(channel, show))
            # Only where one show was asked for: without a show id the films
            # come from many of them, and the first one's name would stand
            # for all the others.
            showname = films[0][2] if (films and show) else ''
            # The one place that may ask the service: a listing about a
            # single show is a single question, and it fills the store for
            # every list the show turns up in afterwards.
            record = self.metadata.forShow(showname, mayAsk=True)
            records = {showname: record} if record else {}
            ui = FilmlistUi.FilmlistUi(self, pLongTitle=False)
            if season:
                films = Seasons.ofSeason(films, int(season))
                leadingItems = None
            else:
                # A show earns a season level or it does not; where it does
                # not, this is the flat listing it has always been.
                (seasons, loose) = Seasons.group(films)
                leadingItems = SeasonUi.SeasonUi(self).generateItems(
                    seasons, channel, show, showname, self.metadata)
                films = loose
            # One request brings the pictures of a whole season, which is
            # worth asking for where the films listed are of one season - the
            # prefetch has usually been there first.
            self.metadata.episodesOf(
                showname, Seasons.soleSeason(films), mayAsk=True)
            stills = self.metadata.stillsOf([showname])
            seasonPosters = self.metadata.seasonsOf([showname])
            params = {'mode': 'films', 'channel': channel or '0', 'show': show or '0'}
            if season:
                params['season'] = season
            (films, nextPage) = self._page(films, params)
            ui.generate(films, leadingItems, records, stills, seasonPosters,
                        nextPage)
            #
        elif mode == 'downloadmv':
            filmIdArray = self._resolveFilmIdsFromParams(
                self.get_arg('id', None),
                self.get_arg('search', None),
                self.get_arg('channel', None),
                self.get_arg('show', None)
            )
            #
            for id in filmIdArray:
                Downloader(self).download_movie(id)
            #
        elif mode == 'downloadep':
            filmIdArray = self._resolveFilmIdsFromParams(
                self.get_arg('id', None),
                self.get_arg('search', None),
                self.get_arg('channel', None),
                self.get_arg('show', None)
            )
            #
            for id in filmIdArray:
                Downloader(self).download_episode(id)
            #
        elif mode == 'playwithsrt':
            filmid = self.get_arg('id', "")
            Downloader(self).play_movie_with_subs(filmid)

        # cleanup saved searches
        if self.get_setting('lastsearch1') != '' and (mode is None or mode != 'newsearch'):
            self.set_setting('lastsearch1', '')
        #
        self.logger.info('request processed: {} sec', time.time() - start)
        #

    def exit(self):
        """ Shutdown of the application """
        self.database.exit()
        self.metadata.exit()

    def show_db_info(self):
        """ Displays current information about the database """
        # pylint: disable=broad-except
        try:
            info = self.database.get_status()
        except Exception as err:
            self.notifier.show_database_error(err)
            return
        heading = self.language(30908)
        infostr = self.language({
            'NONE': 30941,
            'UNINIT': 30942,
            'IDLE': 30943,
            'UPDATING': 30944,
            'ABORTED': 30945
        }.get(info['status'], 30941))
        infostr = self.language(30965) % infostr
        totinfo = self.language(30971) % (
            info['chn'],
            info['shw'],
            info['mov']
            )
        updinfo = self.language(30970) % (
            datetime.fromtimestamp(info['filmUpdate']).isoformat().replace('T', ' '),
            datetime.fromtimestamp(info['lastFullUpdate']).isoformat().replace('T', ' '),
            datetime.fromtimestamp(info['lastUpdate']).isoformat().replace('T', ' ')
            )
        #
        xbmcgui.Dialog().textviewer(
            heading,
            infostr + '\n\n' +
            totinfo + '\n\n' +
            updinfo
        )

    def show_search_menu(self):
        """
        The ways to search, one level below the main menu.

        Everything here is a way in, so nothing on this screen is mixed with
        the searches themselves - those are one level further down.

        A list that would be empty is not offered at all: opening one leads to
        a window holding nothing, which cannot be left other than by going
        back, since Kodi only puts a ".." in front of a list when the user
        asked for parent folder items.
        """
        xbmcplugin.setContent(self.addon_handle, '')
        # New search
        self.add_folder_item(
            30931,
            {'mode': "newsearch"},
            icon=os.path.join(self.path, 'resources', 'icons', 'search-m.png'),
            fanart=os.path.join(self.path, 'resources', 'icons', 'search-f.png')
        )
        # Search history, once there is one
        if len(RecentSearches(self).load().recents) > 0:
            self.add_folder_item(
                30907,
                {'mode': "searchhistory"},
                icon=os.path.join(self.path, 'resources', 'icons', 'results-m.png'),
                fanart=os.path.join(self.path, 'resources', 'icons', 'results-f.png')
            )
        self.end_of_directory()

    def show_search_history(self):
        """ The terms searched for before, nothing else """
        xbmcplugin.setContent(self.addon_handle, '')
        RecentSearches(self).load().populate()
        self.end_of_directory()

    def new_search(self):
        """
        Asks the user to enter his search terms and then
        performs the search and displays the results.
        """
        settingid = 'lastsearch1'
        headingid = 30901
        # are we returning from playback ?
        search = self.get_setting(settingid)
        if search:
            # restore previous search
            self._generateSearch(search)
        else:
            # enter search term
            (search, confirmed) = self.notifier.get_entered_text('', headingid)
            if len(search) > 2 and confirmed is True:
                RecentSearches(self).load().add(search).save()
                #
                rs = self._generateSearch(search)
                if len(rs) > 0:
                    self.set_setting(settingid, search)
            else:
                # pylint: disable=line-too-long
                self.logger.debug(
                    'The following ERROR can be ignored. It is caused by the architecture of the Kodi Plugin Engine')
                self.end_of_directory(False, cache_to_disc=False)

    def _generateFilms(self, fetch, params):
        """
        Lists films from many shows - a search, or what was added lately.

        `fetch` is asked for part of the result, from an offset and at most
        a limit of films. `params` are what this listing was reached by, so
        that the next page is the same listing one page further.

        Each film is of another show here, so the show's poster is what tells
        them apart. One query brings what is stored about all of them.
        """
        (films, following) = self._fill(fetch, self._offset(),
                                        self.settings.getPageSize())
        shownames = [row[SHOWNAME] for row in films]
        FilmlistUi.FilmlistUi(self).generate(
            films, pShowMetadata=self.metadata.forShows(shownames),
            pStills=self.metadata.stillsOf(shownames),
            pSeasonPosters=self.metadata.seasonsOf(shownames),
            pNextPage=None if following is None else self._nextPage(params, following))
        return films

    def _fill(self, fetch, offset, size):
        """
        The films of one page, and where in the result the next page starts.

        The filters drop films after the query, so the page reads on until
        it is full, and one film beyond tells whether another page follows.
        The next page starts at that film, past the ones dropped before it:
        read again there, they would lack the film that dropped them.
        """
        if size <= Paging.UNPAGED:
            return (self._withoutDuplicates(fetch(0, 0)), None)
        rows = []
        while True:
            chunk = fetch(offset + len(rows), size + 1)
            rows.extend(chunk)
            films = self._withoutDuplicates(rows)
            if len(films) > size or len(chunk) <= size:
                break
        if len(films) <= size:
            return (films, None)
        return (films[:size], offset + rows.index(films[size]))

    def _generateSearch(self, search):
        """ Lists what a search found, and hands back the films it showed """
        return self._generateFilms(
            lambda offset, limit: self.database.getQuickSearch(search, offset, limit),
            {'mode': 'research', 'search': search, 'doNotSave': 'true'})

    def _offset(self):
        return max(0, int(self.get_arg('offset', '0') or 0))

    def _nextPage(self, params, offset):
        return self.build_url(dict(params, offset=offset))

    def _page(self, films, params):
        """
        The films of the page that was asked for, and the way to the next.

        For a listing that cannot be cut in the query: a show's seasons are
        worked out from all of its films, so they are all fetched anyway.
        """
        offset = self._offset()
        size = self.settings.getPageSize()
        (shown, following) = Paging.page(films, offset, size)
        if following is None:
            return (shown, None)
        return (shown, self._nextPage(params, following))

    def _gotoShow(self, channel, show, filmId):
        """
        Opens the listing the film is in and puts the cursor on it.

        Which listing that is the show decides: one with seasons keeps its
        episodes behind them, so the film is in the listing of its season.
        """
        films = self._withoutDuplicates(self.database.getFilms(channel, show))
        season = Seasons.seasonOfFilm(films, filmId)
        params = {'mode': 'films', 'channel': channel or '0', 'show': show}
        if season is not None:
            params['season'] = season
            films = Seasons.ofSeason(films, season)
        else:
            (_, films) = Seasons.group(films)
        # The film may be several pages in: the listing is cut where the
        # query put it, so this is the same arithmetic the listing does.
        offset = Paging.pageOf(self._positionOf(films, filmId),
                               self.settings.getPageSize())
        if offset:
            params['offset'] = offset
        Jump().toFilm(self.build_url(params), filmId)

    def _positionOf(self, films, filmId):
        for (index, row) in enumerate(films):
            if row[0] == filmId:
                return index
        return 0

    def _fetchMetadata(self):
        """
        Fetches what is missing right now, rather than waiting for the
        service to get round to it, and reports how far it has come.
        """
        self.notifier.show_metadata_progress()
        try:
            (shows, seasons) = MetadataPrefetch().run(
                self.database, progress=self._reportMetadata)
        finally:
            self.notifier.close_metadata_progress()
        # Whatever came of it, it says so: with everything fetched already
        # the bar is gone again within a second, and pressing a button that
        # answers with nothing at all looks broken.
        if shows or seasons:
            self.notifier.show_notification(
                30993, self.language(30130) % (shows, seasons))
        else:
            self.notifier.show_notification(30993, 30131)

    def _reportMetadata(self, what, done, total):
        message = self.language(30991 if what == 'shows' else 30999) % (done, total)
        self.notifier.update_metadata_progress(
            int(100.0 * done / total) if total else 100, message)

    def _withoutDuplicates(self, films):
        """ Applies the filters the user asked for to a list of films """
        if self.settings.getHideAudioDescription():
            films = Variants.withoutAudioDescription(films)
        if self.settings.getHideSignLanguage():
            films = Variants.withoutSignLanguage(films)
        return films

    def _resolveFilmIdsFromParams(self, filmId, quickSearch, channelId, showId):
        filmIdArray = []
        if filmId is not None:
            filmIdArray.append(filmId)
        elif quickSearch is not None:
            rs = self._withoutDuplicates(self.database.getQuickSearch(quickSearch))
            for id in rs:
                filmIdArray.append(id[0])
        elif showId is not None:
            rs = self._withoutDuplicates(self.database.getFilms(channelId, showId))
            for id in rs:
                filmIdArray.append(id[0])
        return filmIdArray;
