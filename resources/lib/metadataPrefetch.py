# -*- coding: utf-8 -*-
"""
Fetching metadata for shows nobody has opened yet

SPDX-License-Identifier: MIT
"""

# -- Imports ------------------------------------------------
import time
from concurrent.futures import ThreadPoolExecutor

import resources.lib.appContext as appContext
from resources.lib.seasons import splitEpisode
from resources.lib.storeMetadata import StoreMetadata
from resources.lib.tmdb import Tmdb

# -- Constants ----------------------------------------------
# How many requests are in flight at once. Measured against the service:
# 96 shows took 6.6 seconds with eight of them in flight, 1.3 with sixteen,
# and nothing was refused either way. Twelve is what it takes to reach the
# rate below.
THREADS = 12
# What one show costs: one request to search for it, one for its details.
# A season costs one.
REQUESTS_PER_SHOW = 2
REQUESTS_PER_SEASON = 1
# The rate the whole thing is held to: the figure TMDB names, which is also
# far below what the service actually tolerated. At this rate the 9208 shows
# of the current film list take some six minutes.
REQUESTS_PER_SEC = 50
# How long one pass may take. The service thread is doing this, and the film
# database is what it is really for, so it comes back to it regularly and
# picks up the remaining shows on the next round.
PASS_SECONDS = 300


# -- Classes ------------------------------------------------
class MetadataPrefetch(object):
    """
    Fills the metadata store for every show in the film list.

    A listing cannot ask the service itself: it is built once, in the moment
    the user opens it, and asking for its up to 1744 shows would take longer
    than anybody waits. So the shows are looked up here, where taking a while
    costs nobody anything, and the listings find them already stored.
    """

    def __init__(self):
        self.logger = appContext.MVLOGGER.get_new_logger('MetadataPrefetch')
        self.settings = appContext.MVSETTINGS
        self.monitor = appContext.MVMONITOR
        # The film list this store was last brought in line with. Until a new
        # one arrives there is nothing left to look up, so nothing is read.
        self.completed = None

    def run(self, database, progress=None):
        """
        Looks up what the store has no answer for yet.

        `progress` is called with the stage, what is done and what there is
        to do, for a run somebody asked for and is watching. Such a run is
        not cut short either: the five minutes exist so that the service
        gets back to the film database, and nothing waits for that here.

        Returns how many shows and how many seasons it fetched, so that a
        run somebody asked for can say what came of it.
        """
        if database is None or not self.settings.getTmdbEnabled():
            return (0, 0)
        if self.settings.getDatabaseStatus() != 'IDLE':
            # There is no show list to work from before the first update has
            # run, and during one the film database has better things to do.
            return (0, 0)
        lastUpdate = self.settings.getLastUpdate()
        # No film list has arrived yet, so there is nothing to look up - and
        # no film table to ask, either.
        if not lastUpdate or self.completed == lastUpdate:
            return (0, 0)
        service = Tmdb()
        if not service.available():
            return (0, 0)
        store = StoreMetadata()
        try:
            deadline = None if progress else time.time() + PASS_SECONDS
            (shows, complete) = self._shows(store, service, database, deadline, progress)
            if not complete:
                return (shows, 0)
            (seasons, complete) = self._seasons(store, service, database, deadline, progress)
            if complete:
                self.completed = lastUpdate
            return (shows, seasons)
        finally:
            store.exit()

    # -- Internals ------------------------------------------
    def _shows(self, store, service, database, deadline, progress=None):
        """ Looks up the shows: how many, and whether that was all of them """
        shownames = [row[0] for row in database.getAllShownames() if row[0]]
        known = store.knownShows()
        missing = [name for name in shownames if name not in known]
        if not missing:
            return (0, True)

        def remember(name, record):
            store.putShow(name, record)

        return self._fetch(missing, service.lookupShow, remember,
                           REQUESTS_PER_SHOW, deadline, 'shows', progress)

    def _seasons(self, store, service, database, deadline, progress=None):
        """
        Looks up the episodes of every season the film list names.

        One request per season, and only for a season of a show TMDB knows.
        The pictures are what a listing shows for an episode, and a listing
        cannot fetch them itself: a search can hold films of a hundred
        seasons.
        """
        missing = self._missingSeasons(store, database)
        if not missing:
            return (0, True)

        def lookup(job):
            return service.lookupSeason(job[0], job[2])

        def remember(job, stills):
            if stills is not None:
                store.putEpisodes(job[1], job[2], stills)

        return self._fetch(missing, lookup, remember,
                           REQUESTS_PER_SEASON, deadline, 'seasons', progress)

    def _missingSeasons(self, store, database):
        """ The seasons whose episodes are not stored yet, as (id, show, season) """
        pairs = set()
        for row in database.getEpisodeTitles():
            (_, season, _) = splitEpisode(row[1] or '')
            if row[0] and season is not None:
                pairs.add((row[0], season))
        records = store.getShows(set(name for (name, _) in pairs))
        return [(records[name]['tmdbid'], name, season)
                for (name, season) in sorted(pairs)
                if name in records and not store.episodesKnown(name, season)]

    def _fetch(self, jobs, lookup, remember, cost, deadline, what, progress=None):
        """
        Returns how many it fetched and whether that was the whole list.

        The only thing logged is this: one line when a stage starts and one
        when it stops. Whatever the service answered per show is nobody's
        business - it used to be a debug line per show, thousands of them.
        """
        self.logger.info('Fetching {} {}', len(jobs), what)
        began = time.time()
        done = 0
        with ThreadPoolExecutor(max_workers=THREADS) as pool:
            for start in range(0, len(jobs), THREADS):
                if self.monitor.abort_requested():
                    break
                if deadline is not None and time.time() > deadline:
                    break
                if progress:
                    progress(what, done, len(jobs))
                batch = jobs[start:start + THREADS]
                batchBegan = time.time()
                for (job, answer) in zip(batch, pool.map(lookup, batch)):
                    remember(job, answer)
                done += len(batch)
                spare = (cost * len(batch) / float(REQUESTS_PER_SEC)
                         - (time.time() - batchBegan))
                if spare > 0 and self.monitor.wait_for_abort(spare):
                    break
        self.logger.info('Fetched {} of {} {} in {} sec',
                         done, len(jobs), what, int(time.time() - began))
        return (done, done == len(jobs))
