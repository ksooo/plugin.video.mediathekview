# -*- coding: utf-8 -*-
"""
What an external service knows about a show, kept between sessions

SPDX-License-Identifier: MIT
"""

# -- Imports ------------------------------------------------
import json
import os
import sqlite3
import time

import resources.lib.appContext as appContext
import resources.lib.mvutils as mvutils

# -- Constants ----------------------------------------------
# Its own file, deliberately not a table in the film database: with fast
# native updates that file is MediathekView's own, downloaded and put in
# place as it comes, so anything we wrote into it would be gone by the next
# day. The query cache is no place for it either - that is purged on every
# update, and rightly so, while a poster stays the same.
FILENAME = 'metadata.db'
# Raised when the columns change. The whole file is a cache, so the cheapest
# migration is to throw it away and ask again.
SCHEMA_VERSION = 1
# How long "nothing found" is believed. The service keeps growing, and a show
# that was unknown in spring may be there in autumn. A match, once found, is
# kept until somebody deletes the file.
MISS_SECONDS = 30 * 86400

_SHOW_COLUMNS = ('tmdbid', 'checked', 'poster', 'fanart', 'plot', 'genres',
                 'premiered', 'rating', 'votes', 'mpaa', 'imdbid')
# How many names go into one IN clause. SQLite takes 999 parameters by
# default, and one of them is spent elsewhere in the statement.
_QUERY_LIMIT = 900


# -- Classes ------------------------------------------------
class StoreMetadata(object):
    """ The metadata store """

    def __init__(self):
        self.logger = appContext.MVLOGGER.get_new_logger('StoreMetadata')
        self.settings = appContext.MVSETTINGS
        self.dbfile = os.path.join(self.settings.getDatapath(), FILENAME)
        self.conn = None

    def getConnection(self):
        if self.conn is None:
            self.conn = sqlite3.connect(self.dbfile, timeout=10)
            if self._version() != SCHEMA_VERSION:
                self._create()
        return self.conn

    def exit(self):
        if self.conn is not None:
            self.conn.commit()
            self.conn.close()
            self.conn = None

    def reset(self):
        """ Forgets everything, by removing the file """
        self.exit()
        mvutils.file_remove(self.dbfile)

    def forget(self, showname):
        """
        Forgets one show, so that it is asked about again.

        The cure for a wrong match: nothing else can put it right, since
        without a library there is no dialog to choose the artwork in.
        """
        # pylint: disable=broad-except
        try:
            connection = self.getConnection()
            connection.execute('DELETE FROM show WHERE showname = ?', (showname,))
            connection.execute('DELETE FROM season WHERE showname = ?', (showname,))
            connection.execute('DELETE FROM episode WHERE showname = ?', (showname,))
            connection.commit()
        except Exception as err:
            self.logger.error('Failed to write the metadata store: {}', err)

    # -- Shows ----------------------------------------------
    def getShow(self, showname):
        """
        What is stored about a show.

        `None` means nobody has asked lately - so ask. A record whose
        `tmdbid` is `None` means somebody did ask and the service had
        nothing, which is an answer in itself and saves asking again.
        """
        # pylint: disable=broad-except
        try:
            cursor = self.getConnection().cursor()
            cursor.execute(
                'SELECT %s FROM show WHERE showname = ?' % ', '.join(_SHOW_COLUMNS),
                (showname,))
            row = cursor.fetchone()
            cursor.close()
        except Exception as err:
            self.logger.error('Failed to read the metadata store: {}', err)
            return None
        if row is None:
            return None
        record = dict(zip(_SHOW_COLUMNS, row))
        if record['tmdbid'] is None and record['checked'] < time.time() - MISS_SECONDS:
            return None
        record['genres'] = json.loads(record['genres']) if record['genres'] else []
        return record

    def getShows(self, shownames):
        """
        What is stored about each of these shows, by name.

        For a listing of films from many shows: one query rather than one per
        film. Shows the store knows nothing about are simply absent, as are
        the ones it only knows to be unknown.
        """
        names = [name for name in set(shownames or []) if name]
        records = {}
        # pylint: disable=broad-except
        try:
            cursor = self.getConnection().cursor()
            for at in range(0, len(names), _QUERY_LIMIT):
                chunk = names[at:at + _QUERY_LIMIT]
                cursor.execute(
                    'SELECT showname, %s FROM show WHERE showname IN (%s)'
                    % (', '.join(_SHOW_COLUMNS), ', '.join('?' * len(chunk))), chunk)
                for row in cursor.fetchall():
                    record = dict(zip(_SHOW_COLUMNS, row[1:]))
                    if record['tmdbid'] is None:
                        continue
                    record['genres'] = (json.loads(record['genres'])
                                        if record['genres'] else [])
                    records[row[0]] = record
            cursor.close()
        except Exception as err:
            self.logger.error('Failed to read the metadata store: {}', err)
        return records

    def knownShows(self):
        """
        The names of all shows the store has an answer for.

        A miss that has expired is not among them, so that it is asked about
        again. Read in one go because the prefetch asks about thousands of
        shows at a time.
        """
        # pylint: disable=broad-except
        try:
            cursor = self.getConnection().cursor()
            cursor.execute('SELECT showname FROM show'
                           ' WHERE tmdbid IS NOT NULL OR checked >= ?',
                           (time.time() - MISS_SECONDS,))
            rows = cursor.fetchall()
            cursor.close()
        except Exception as err:
            self.logger.error('Failed to read the metadata store: {}', err)
            return set()
        return set(row[0] for row in rows)

    def putShow(self, showname, record=None):
        """
        Stores what was found for a show, or that nothing was.

        Called with no record it writes the fact that the service was asked
        and had nothing. The seasons come with the show's own answer and are
        stored along with it.
        """
        values = dict.fromkeys(_SHOW_COLUMNS)
        values.update(record or {})
        values['checked'] = int(time.time())
        values['genres'] = json.dumps(values['genres']) if values.get('genres') else None
        # pylint: disable=broad-except
        try:
            connection = self.getConnection()
            connection.execute(
                'INSERT OR REPLACE INTO show (showname, %s) VALUES (?%s)'
                % (', '.join(_SHOW_COLUMNS), ', ?' * len(_SHOW_COLUMNS)),
                (showname,) + tuple(values[column] for column in _SHOW_COLUMNS))
            for (number, season) in ((record or {}).get('seasons') or {}).items():
                self._putSeason(connection, showname, number,
                                season.get('poster'), season.get('plot'))
            connection.commit()
        except Exception as err:
            self.logger.error('Failed to write the metadata store: {}', err)

    # -- Seasons --------------------------------------------
    def getSeason(self, showname, season):
        """ What is stored about one season, or `None` """
        # pylint: disable=broad-except
        try:
            cursor = self.getConnection().cursor()
            cursor.execute(
                'SELECT poster, plot FROM season WHERE showname = ? AND season = ?',
                (showname, season))
            row = cursor.fetchone()
            cursor.close()
        except Exception as err:
            self.logger.error('Failed to read the metadata store: {}', err)
            return None
        return {'poster': row[0], 'plot': row[1]} if row else None

    def getSeasons(self, shownames):
        """
        The poster of every stored season of these shows, by show and season.

        For a listing of films: one query rather than one per film.
        """
        names = [name for name in set(shownames or []) if name]
        posters = {}
        # pylint: disable=broad-except
        try:
            cursor = self.getConnection().cursor()
            for at in range(0, len(names), _QUERY_LIMIT):
                chunk = names[at:at + _QUERY_LIMIT]
                cursor.execute(
                    'SELECT showname, season, poster FROM season'
                    ' WHERE showname IN (%s)' % ', '.join('?' * len(chunk)), chunk)
                for row in cursor.fetchall():
                    if row[2]:
                        posters[(row[0], row[1])] = row[2]
            cursor.close()
        except Exception as err:
            self.logger.error('Failed to read the metadata store: {}', err)
        return posters

    def putSeason(self, showname, season, poster=None, plot=None):
        """ Stores what was found for one season """
        # pylint: disable=broad-except
        try:
            connection = self.getConnection()
            self._putSeason(connection, showname, season, poster, plot)
            connection.commit()
        except Exception as err:
            self.logger.error('Failed to write the metadata store: {}', err)

    def _putSeason(self, connection, showname, season, poster, plot):
        connection.execute(
            'INSERT OR REPLACE INTO season (showname, season, poster, plot)'
            ' VALUES (?, ?, ?, ?)', (showname, season, poster, plot))

    # -- Episodes -------------------------------------------
    def episodesKnown(self, showname, season):
        """ Whether the episodes of this season have been fetched already """
        # pylint: disable=broad-except
        try:
            cursor = self.getConnection().cursor()
            cursor.execute('SELECT checked FROM season WHERE showname = ? AND season = ?',
                           (showname, season))
            row = cursor.fetchone()
            cursor.close()
        except Exception as err:
            self.logger.error('Failed to read the metadata store: {}', err)
            return False
        return bool(row and row[0])

    def getEpisodes(self, showname, season):
        """ The still of every episode of a season that has one """
        # pylint: disable=broad-except
        try:
            cursor = self.getConnection().cursor()
            cursor.execute(
                'SELECT episode, still FROM episode WHERE showname = ? AND season = ?',
                (showname, season))
            rows = cursor.fetchall()
            cursor.close()
        except Exception as err:
            self.logger.error('Failed to read the metadata store: {}', err)
            return {}
        return dict((row[0], row[1]) for row in rows if row[1])

    def getStills(self, shownames):
        """
        Every stored episode picture of these shows.

        Keyed by show, season and episode, because a listing of films can
        hold several shows and several seasons of them. For a listing of
        films from many shows: one query rather than one per film.
        """
        names = [name for name in set(shownames or []) if name]
        stills = {}
        # pylint: disable=broad-except
        try:
            cursor = self.getConnection().cursor()
            for at in range(0, len(names), _QUERY_LIMIT):
                chunk = names[at:at + _QUERY_LIMIT]
                cursor.execute(
                    'SELECT showname, season, episode, still FROM episode'
                    ' WHERE showname IN (%s)' % ', '.join('?' * len(chunk)), chunk)
                for row in cursor.fetchall():
                    if row[3]:
                        stills[(row[0], row[1], row[2])] = row[3]
            cursor.close()
        except Exception as err:
            self.logger.error('Failed to read the metadata store: {}', err)
        return stills

    def putEpisodes(self, showname, season, stills):
        """
        Stores the stills of a season, and that the season was fetched.

        A season whose episodes have no artwork stores nothing but the fact
        that it was asked about, which is what stops it being asked again.
        """
        # pylint: disable=broad-except
        try:
            connection = self.getConnection()
            for (number, still) in (stills or {}).items():
                connection.execute(
                    'INSERT OR REPLACE INTO episode (showname, season, episode, still)'
                    ' VALUES (?, ?, ?, ?)', (showname, season, number, still))
            self._touchSeason(connection, showname, season)
            connection.commit()
        except Exception as err:
            self.logger.error('Failed to write the metadata store: {}', err)

    def _touchSeason(self, connection, showname, season):
        """
        Notes that a season was fetched, without disturbing its own artwork.

        INSERT OR REPLACE would wipe the poster and the description that came
        with the show, so the row is updated where it is already there.
        """
        cursor = connection.cursor()
        cursor.execute(
            'UPDATE season SET checked = ? WHERE showname = ? AND season = ?',
            (int(time.time()), showname, season))
        updated = cursor.rowcount
        cursor.close()
        if not updated:
            connection.execute(
                'INSERT INTO season (showname, season, checked) VALUES (?, ?, ?)',
                (showname, season, int(time.time())))

    # -- Internals ------------------------------------------
    def _version(self):
        cursor = self.conn.cursor()
        cursor.execute('PRAGMA user_version')
        version = cursor.fetchone()[0]
        cursor.close()
        return version

    def _create(self):
        self.logger.debug('Setting up the metadata store in {}', self.dbfile)
        self.conn.executescript("""
            DROP TABLE IF EXISTS show;
            DROP TABLE IF EXISTS season;
            DROP TABLE IF EXISTS episode;
            CREATE TABLE show (
                showname  TEXT PRIMARY KEY,
                tmdbid    INTEGER,
                checked   INTEGER NOT NULL,
                poster    TEXT,
                fanart    TEXT,
                plot      TEXT,
                genres    TEXT,
                premiered TEXT,
                rating    REAL,
                votes     INTEGER,
                mpaa      TEXT,
                imdbid    TEXT);
            CREATE TABLE season (
                showname TEXT NOT NULL,
                season   INTEGER NOT NULL,
                poster   TEXT,
                plot     TEXT,
                -- When the episodes of this season were fetched. A season
                -- whose episodes have no artwork at all leaves no episode
                -- rows behind, so without this it would be fetched again
                -- every time it is opened.
                checked  INTEGER,
                PRIMARY KEY (showname, season));
            CREATE TABLE episode (
                showname TEXT NOT NULL,
                season   INTEGER NOT NULL,
                episode  INTEGER NOT NULL,
                still    TEXT,
                PRIMARY KEY (showname, season, episode));
            PRAGMA user_version = %d;
        """ % SCHEMA_VERSION)
        self.conn.commit()
