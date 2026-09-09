# -*- coding: utf-8 -*-
"""
What is known about a show beyond what the film list says

SPDX-License-Identifier: MIT
"""

# -- Imports ------------------------------------------------
import resources.lib.appContext as appContext
from resources.lib.storeMetadata import StoreMetadata
from resources.lib.tmdb import Tmdb


# -- Classes ------------------------------------------------
class Metadata(object):
    """
    The store and the service, and the rule for when either is consulted.

    A plugin builds its listing once and then the script ends - nothing tells
    it that an item has scrolled into view, so everything a listing shows has
    to be known while it is built. Asking the service takes a second, which
    is bearable once and out of the question for the 1746 shows a channel
    can hold. So a listing of many shows reads the store and nothing else,
    while a listing that is about one show may ask, and thereby fills the
    store for the next time the show turns up in a list.
    """

    def __init__(self):
        self.logger = appContext.MVLOGGER.get_new_logger('Metadata')
        self.settings = appContext.MVSETTINGS
        self.store = None
        self.service = None

    def enabled(self):
        """
        Whether stored metadata may be used at all.

        The switch governs the whole feature, not only the asking: turning it
        off puts the listings back to how they look without it.
        """
        return bool(self.settings.getTmdbEnabled())

    def forShow(self, showname, mayAsk=False):
        """
        What is known about a show, or `None`.

        Reads the store; asks the service only when told to and only when the
        store has no answer yet. Whatever comes back is stored, including the
        fact that there was nothing, so the question is asked once.
        """
        if not showname or not self.enabled():
            return None
        record = self._getStore().getShow(showname)
        if record is not None:
            return record if record['tmdbid'] is not None else None
        if not mayAsk:
            return None
        service = self._getService()
        if not service.available():
            return None
        found = service.lookupShow(showname)
        self._getStore().putShow(showname, found)
        return found

    def forShows(self, shownames):
        """
        What is known about each of these shows, by name.

        Reads the store and never asks: this is for a listing of films from
        many shows, where asking would mean one request per show. What the
        background prefetch has already found turns up here.
        """
        if not self.enabled():
            return {}
        return self._getStore().getShows(shownames)

    def seasonsOf(self, shownames):
        """
        The stored season posters of these shows, by show and season.

        Reads the store and never asks. A film's own picture is what a list
        shows; this is what the information dialog puts behind it.
        """
        if not self.enabled():
            return {}
        return self._getStore().getSeasons(shownames)

    def episodesOf(self, showname, season, mayAsk=False):
        """
        The still of every episode of a season that has one.

        One request covers a whole season, so this is worth asking for where
        the films on screen belong to a single one. A season whose episodes
        carry no stills is remembered as asked about, not as unknown.
        """
        if not showname or season is None or not self.enabled():
            return {}
        store = self._getStore()
        if not store.episodesKnown(showname, season):
            if not mayAsk:
                return {}
            record = self.forShow(showname, mayAsk=True)
            if not record:
                return {}
            service = self._getService()
            if not service.available():
                return {}
            stills = service.lookupSeason(record['tmdbid'], season)
            if stills is None:
                return {}
            store.putEpisodes(showname, season, stills)
        return store.getEpisodes(showname, season)

    def stillsOf(self, shownames):
        """
        The stored episode pictures of these shows, by show, season, episode.

        Reads the store and never asks: a listing of films can hold a
        hundred shows. What the background prefetch has found turns up here.
        """
        if not self.enabled():
            return {}
        return self._getStore().getStills(shownames)

    def forget(self, showname):
        """ Drops what is stored about a show and asks again """
        if not showname or not self.enabled():
            return None
        self._getStore().forget(showname)
        return self.forShow(showname, mayAsk=True)

    def discardAll(self):
        """ Drops everything that was ever stored """
        self._getStore().reset()

    def exit(self):
        if self.store is not None:
            self.store.exit()
            self.store = None

    # -- Internals ------------------------------------------
    def _getStore(self):
        if self.store is None:
            self.store = StoreMetadata()
        return self.store

    def _getService(self):
        if self.service is None:
            self.service = Tmdb()
        return self.service

    def seasonOf(self, showname, season):
        """ What is known about one season, or `None` """
        if not showname or not self.enabled():
            return None
        return self._getStore().getSeason(showname, season)
