# -*- coding: utf-8 -*-
"""
Tests for the store that keeps what an external service knows

SPDX-License-Identifier: MIT
"""

import os
import shutil
import sqlite3
import tempfile
import time
import unittest

from tests import support

support.init_app_context()

import resources.lib.storeMetadata as storeMetadata
from resources.lib.storeMetadata import StoreMetadata

RECORD = {
    'tmdbid': 12345,
    'poster': '/poster.jpg',
    'fanart': '/fanart.jpg',
    'plot': 'Eine Klinik in Leipzig.',
    'genres': ['Drama', 'Arzt'],
    'premiered': '1998-10-26',
    'rating': 7.4,
    'votes': 120,
    'mpaa': 'FSK 12',
    'imdbid': 'tt0176095',
}


class StoreMetadataTest(unittest.TestCase):

    def setUp(self):
        self.datapath = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.datapath)
        support.init_app_context(
            settings=support.Settings(datapath=self.datapath))
        self.store = StoreMetadata()
        self.addCleanup(self.store.exit)

    def _reopen(self):
        """A second store on the same file, as the next plugin call would be."""
        self.store.exit()
        store = StoreMetadata()
        self.addCleanup(store.exit)
        return store

    def test_a_show_nobody_asked_about_is_unknown(self):
        self.assertIsNone(self.store.getShow('In aller Freundschaft'))

    def test_what_was_found_comes_back(self):
        self.store.putShow('In aller Freundschaft', RECORD)
        record = self.store.getShow('In aller Freundschaft')
        self.assertEqual(record['tmdbid'], 12345)
        self.assertEqual(record['poster'], '/poster.jpg')
        self.assertEqual(record['plot'], 'Eine Klinik in Leipzig.')
        self.assertEqual(record['rating'], 7.4)
        self.assertEqual(record['imdbid'], 'tt0176095')

    def test_the_genres_survive_as_a_list(self):
        self.store.putShow('In aller Freundschaft', RECORD)
        self.assertEqual(self.store.getShow('In aller Freundschaft')['genres'],
                         ['Drama', 'Arzt'])

    def test_it_outlives_the_session(self):
        self.store.putShow('Der Bergdoktor', RECORD)
        self.assertEqual(self._reopen().getShow('Der Bergdoktor')['tmdbid'], 12345)

    def test_asking_again_replaces_the_answer(self):
        self.store.putShow('Der Bergdoktor', RECORD)
        self.store.putShow('Der Bergdoktor', dict(RECORD, tmdbid=999, poster='/neu.jpg'))
        record = self.store.getShow('Der Bergdoktor')
        self.assertEqual(record['tmdbid'], 999)
        self.assertEqual(record['poster'], '/neu.jpg')

    def test_a_miss_is_an_answer_too(self):
        # Otherwise every listing of Tagesschau asks the service again.
        self.store.putShow('Tagesschau')
        record = self.store.getShow('Tagesschau')
        self.assertIsNotNone(record, 'the miss has to be remembered')
        self.assertIsNone(record['tmdbid'])

    def test_a_miss_is_asked_again_after_a_while(self):
        # The service keeps growing.
        self.store.putShow('Tagesschau')
        old = int(time.time()) - storeMetadata.MISS_SECONDS - 1
        connection = self.store.getConnection()
        connection.execute('UPDATE show SET checked = ?', (old,))
        connection.commit()
        self.assertIsNone(self.store.getShow('Tagesschau'))

    def test_a_match_is_kept_however_old(self):
        self.store.putShow('Der Bergdoktor', RECORD)
        old = int(time.time()) - storeMetadata.MISS_SECONDS * 10
        connection = self.store.getConnection()
        connection.execute('UPDATE show SET checked = ?', (old,))
        connection.commit()
        self.assertEqual(self.store.getShow('Der Bergdoktor')['tmdbid'], 12345)

    def test_seasons_are_kept_per_show(self):
        self.store.putSeason('Der Bergdoktor', 19, poster='/s19.jpg', plot='Staffel 19')
        self.store.putSeason('Der Bergdoktor', 18, poster='/s18.jpg')
        self.assertEqual(self.store.getSeason('Der Bergdoktor', 19),
                         {'poster': '/s19.jpg', 'plot': 'Staffel 19'})
        self.assertEqual(self.store.getSeason('Der Bergdoktor', 18)['poster'], '/s18.jpg')
        self.assertIsNone(self.store.getSeason('Der Bergdoktor', 1))

    def test_it_lives_beside_the_film_database_not_in_it(self):
        # The film database is MediathekView's own file, replaced whole on
        # every update, so anything stored in it would not last the day.
        self.store.putShow('Der Bergdoktor', RECORD)
        self.assertTrue(os.path.exists(os.path.join(self.datapath, storeMetadata.FILENAME)))
        self.assertFalse(os.path.exists(os.path.join(self.datapath, 'filmliste-v3.db')))

    def test_a_file_from_an_older_schema_is_discarded(self):
        self.store.putShow('Der Bergdoktor', RECORD)
        self.store.exit()
        connection = sqlite3.connect(os.path.join(self.datapath, storeMetadata.FILENAME))
        connection.execute('PRAGMA user_version = 0')
        connection.commit()
        connection.close()
        store = StoreMetadata()
        self.addCleanup(store.exit)
        self.assertIsNone(store.getShow('Der Bergdoktor'))

    def test_reset_forgets_everything(self):
        self.store.putShow('Der Bergdoktor', RECORD)
        self.store.reset()
        self.assertIsNone(StoreMetadata().getShow('Der Bergdoktor'))

    def test_a_broken_file_is_reported_rather_than_raised(self):
        # A listing must not fall over because the cache is unreadable.
        self.store.exit()
        with open(os.path.join(self.datapath, storeMetadata.FILENAME), 'w') as handle:
            handle.write('this is not a database')
        store = StoreMetadata()
        self.addCleanup(store.exit)
        self.assertIsNone(store.getShow('Der Bergdoktor'))
        import resources.lib.appContext as appContext
        logged = [text for (level, text) in appContext.MVLOGGER.messages
                  if level == 'error']
        self.assertTrue(logged, 'the reason has to reach the log')

    def test_the_seasons_come_with_the_show(self):
        # They are part of the show's own answer, so they are stored with it.
        self.store.putShow('In aller Freundschaft', dict(RECORD, seasons={
            1: {'poster': '/s1.jpg', 'plot': 'Der Anfang.'}}))
        self.assertEqual(self.store.getSeason('In aller Freundschaft', 1),
                         {'poster': '/s1.jpg', 'plot': 'Der Anfang.'})

    # -- Many shows at once ---------------------------------
    def test_a_listing_reads_its_shows_in_one_go(self):
        self.store.putShow('In aller Freundschaft', RECORD)
        self.store.putShow('Der Bergdoktor', dict(RECORD, tmdbid=14509))
        records = self.store.getShows(['In aller Freundschaft', 'Der Bergdoktor'])
        self.assertEqual(sorted(records), ['Der Bergdoktor', 'In aller Freundschaft'])
        self.assertEqual(records['In aller Freundschaft']['genres'], ['Drama', 'Arzt'])

    def test_a_show_nobody_asked_about_is_simply_absent(self):
        self.store.putShow('In aller Freundschaft', RECORD)
        self.assertEqual(list(self.store.getShows(
            ['In aller Freundschaft', 'Tagesschau'])), ['In aller Freundschaft'])

    def test_a_show_the_service_did_not_know_is_absent_too(self):
        self.store.putShow('Tagesschau')
        self.assertEqual(self.store.getShows(['Tagesschau']), {})

    def test_more_names_than_a_statement_takes(self):
        # SQLite allows 999 parameters, and a listing can hold more shows.
        names = ['Sendung %d' % number for number in range(2000)]
        for name in names[:1500]:
            self.store.putShow(name, RECORD)
        self.assertEqual(len(self.store.getShows(names)), 1500)

    def test_no_names_at_all(self):
        self.assertEqual(self.store.getShows([]), {})
        self.assertEqual(self.store.getShows(['', None]), {})

    def test_a_listing_reads_the_season_posters_in_one_go(self):
        self.store.putSeason('In aller Freundschaft', 1, '/s1.jpg', None)
        self.store.putSeason('In aller Freundschaft', 2, None, 'Nur ein Text.')
        self.store.putSeason('Der Bergdoktor', 18, '/berg18.jpg', None)
        posters = self.store.getSeasons(['In aller Freundschaft', 'Der Bergdoktor'])
        self.assertEqual(posters, {('In aller Freundschaft', 1): '/s1.jpg',
                                   ('Der Bergdoktor', 18): '/berg18.jpg'})

    def test_no_season_posters_asked_for(self):
        self.assertEqual(self.store.getSeasons([]), {})

    # -- What is known already ------------------------------
    def test_a_show_that_was_found_is_known(self):
        self.store.putShow('In aller Freundschaft', RECORD)
        self.assertEqual(self.store.knownShows(), set(['In aller Freundschaft']))

    def test_a_show_that_was_not_found_is_known_too(self):
        # There is no point asking about it again for a while.
        self.store.putShow('Tagesschau')
        self.assertEqual(self.store.knownShows(), set(['Tagesschau']))

    def test_a_miss_that_has_expired_is_not_known_any_more(self):
        self.store.putShow('Tagesschau')
        self.store.getConnection().execute(
            'UPDATE show SET checked = ?',
            (time.time() - storeMetadata.MISS_SECONDS - 1,))
        self.assertEqual(self.store.knownShows(), set())

    def test_nothing_is_known_of_an_empty_store(self):
        self.assertEqual(self.store.knownShows(), set())

    # -- Episodes -------------------------------------------
    def test_nothing_is_known_before_anybody_asked(self):
        self.assertFalse(self.store.episodesKnown('Die Rosenheim-Cops', 24))
        self.assertEqual(self.store.getEpisodes('Die Rosenheim-Cops', 24), {})

    def test_what_was_stored_comes_back(self):
        self.store.putEpisodes('Die Rosenheim-Cops', 24,
                               {1: 'eins.jpg', 2: 'zwei.jpg'})
        self.assertTrue(self.store.episodesKnown('Die Rosenheim-Cops', 24))
        self.assertEqual(self.store.getEpisodes('Die Rosenheim-Cops', 24),
                         {1: 'eins.jpg', 2: 'zwei.jpg'})

    def test_a_season_without_any_pictures_is_still_marked_as_asked_about(self):
        # Otherwise it would be fetched again every time it is opened.
        self.store.putEpisodes('In aller Freundschaft', 1, {})
        self.assertTrue(self.store.episodesKnown('In aller Freundschaft', 1))
        self.assertEqual(self.store.getEpisodes('In aller Freundschaft', 1), {})

    def test_the_seasons_own_artwork_survives(self):
        self.store.putSeason('Die Rosenheim-Cops', 24, 'poster.jpg', 'Worum es geht.')
        self.store.putEpisodes('Die Rosenheim-Cops', 24, {1: 'eins.jpg'})
        self.assertEqual(self.store.getSeason('Die Rosenheim-Cops', 24),
                         {'poster': 'poster.jpg', 'plot': 'Worum es geht.'})

    def test_the_seasons_are_kept_apart(self):
        self.store.putEpisodes('Die Rosenheim-Cops', 23, {1: 'alt.jpg'})
        self.store.putEpisodes('Die Rosenheim-Cops', 24, {1: 'neu.jpg'})
        self.assertEqual(self.store.getEpisodes('Die Rosenheim-Cops', 23),
                         {1: 'alt.jpg'})
        self.assertEqual(self.store.getEpisodes('Die Rosenheim-Cops', 24),
                         {1: 'neu.jpg'})

    def test_forgetting_a_show_drops_its_episodes(self):
        self.store.putEpisodes('Die Rosenheim-Cops', 24, {1: 'eins.jpg'})
        self.store.forget('Die Rosenheim-Cops')
        self.assertFalse(self.store.episodesKnown('Die Rosenheim-Cops', 24))
        self.assertEqual(self.store.getEpisodes('Die Rosenheim-Cops', 24), {})

    def test_a_listing_reads_the_pictures_of_many_shows_in_one_go(self):
        self.store.putEpisodes('Die Rosenheim-Cops', 24, {1: 'cops.jpg'})
        self.store.putEpisodes('Der Bergdoktor', 18, {2: 'berg.jpg'})
        self.store.putEpisodes('Tagesschau', 1, {})
        stills = self.store.getStills(
            ['Die Rosenheim-Cops', 'Der Bergdoktor', 'Tagesschau', 'Löwenzahn'])
        self.assertEqual(stills, {('Die Rosenheim-Cops', 24, 1): 'cops.jpg',
                                  ('Der Bergdoktor', 18, 2): 'berg.jpg'})

    def test_no_pictures_asked_for(self):
        self.assertEqual(self.store.getStills([]), {})

    def test_what_is_stored_outlives_the_session(self):
        self.store.putEpisodes('Die Rosenheim-Cops', 24, {1: 'eins.jpg'})
        self.assertEqual(self._reopen().getEpisodes('Die Rosenheim-Cops', 24),
                         {1: 'eins.jpg'})


if __name__ == '__main__':
    unittest.main()
