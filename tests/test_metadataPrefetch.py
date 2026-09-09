# -*- coding: utf-8 -*-
"""
Tests for looking up shows before anybody opens them

SPDX-License-Identifier: MIT
"""

import shutil
import tempfile
import unittest

from tests import support

support.init_app_context()

import resources.lib.metadataPrefetch as metadataPrefetch
from resources.lib.metadataPrefetch import MetadataPrefetch
from resources.lib.storeMetadata import StoreMetadata

SHOWS = ['Der Bergdoktor', 'Die Rosenheim-Cops', 'In aller Freundschaft',
         'Tagesschau', 'Löwenzahn']
# What the film list holds for those shows: the season and episode sit
# inside the title, so this is what the prefetch reads them from.
TITLES = [('Der Bergdoktor', 'Der Weg zurück (S18/E01)'),
          ('Der Bergdoktor', 'Alte Wunden (S18/E02)'),
          ('Der Bergdoktor', 'Heimkehr (S17/E01)'),
          ('Die Rosenheim-Cops', 'Der Tote im Kofferraum (S24/E01)'),
          ('Tagesschau', 'Tagesschau 20:00 Uhr')]


class Database(object):
    """Stands in for the film database."""

    def __init__(self, shownames=None, titles=None):
        self.shownames = SHOWS if shownames is None else shownames
        self.titles = TITLES if titles is None else titles
        self.asked = 0
        self.askedTitles = 0

    def getAllShownames(self):
        self.asked += 1
        return [(name,) for name in self.shownames]

    def getEpisodeTitles(self):
        self.askedTitles += 1
        return list(self.titles)


class Service(object):
    """Stands in for the TMDB client and records what it was asked."""

    def __init__(self, known=None, availableToo=True):
        self.asked = []
        self.askedSeasons = []
        self.stills = {1: 'eins.jpg', 2: 'zwei.jpg'}
        self.known = SHOWS if known is None else known
        self.availableToo = availableToo

    def available(self):
        return self.availableToo

    def lookupShow(self, showname):
        self.asked.append(showname)
        if showname not in self.known:
            return None
        return {'tmdbid': self.identifier(showname), 'poster': showname + '.jpg',
                'seasons': {1: {'poster': showname + '-s1.jpg', 'plot': None}}}

    def lookupSeason(self, tmdbid, season):
        self.askedSeasons.append((tmdbid, season))
        return self.stills

    def identifier(self, showname):
        return abs(hash(showname)) % 100000


class PrefetchTest(unittest.TestCase):

    def setUp(self):
        self.datapath = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.datapath)
        self.monitor = support.Monitor()
        self.settings = None
        self._context(tmdbEnabled=True)
        self.service = Service()
        self.addCleanup(setattr, metadataPrefetch, 'Tmdb', metadataPrefetch.Tmdb)
        metadataPrefetch.Tmdb = lambda: self.service

    def _context(self, **settings):
        settings.setdefault('datapath', self.datapath)
        settings.setdefault('tmdbToken', 'eyJtoken')
        # A film list has arrived; without one there is nothing to look up.
        settings.setdefault('lastUpdate', 1756000000)
        self.settings = support.Settings(**settings)
        support.init_app_context(settings=self.settings, monitor=self.monitor)

    def _store(self):
        store = StoreMetadata()
        self.addCleanup(store.exit)
        return store

    def _run(self, database=Database):
        prefetch = MetadataPrefetch()
        prefetch.run(Database() if database is Database else database)
        return prefetch

    def test_every_show_is_looked_up(self):
        self._run()
        self.assertEqual(sorted(self.service.asked), sorted(SHOWS))

    def test_what_was_found_is_stored_for_the_listings(self):
        self._run()
        store = self._store()
        self.assertEqual(store.getShow('Der Bergdoktor')['poster'],
                         'Der Bergdoktor.jpg')
        self.assertEqual(store.getSeason('Der Bergdoktor', 1)['poster'],
                         'Der Bergdoktor-s1.jpg')

    def test_a_show_the_service_does_not_know_is_stored_as_a_miss(self):
        self.service.known = ['Der Bergdoktor']
        self._run()
        store = self._store()
        self.assertIsNone(store.getShow('Tagesschau')['tmdbid'])

    def test_what_is_stored_is_not_looked_up_again(self):
        self._store().putShow('Der Bergdoktor', {'tmdbid': 14509})
        self._run()
        self.assertNotIn('Der Bergdoktor', self.service.asked)
        self.assertIn('Löwenzahn', self.service.asked)

    def test_the_episodes_of_every_season_the_film_list_names_are_fetched(self):
        self._run()
        identifier = self.service.identifier
        expected = sorted([(identifier('Der Bergdoktor'), 17),
                           (identifier('Der Bergdoktor'), 18),
                           (identifier('Die Rosenheim-Cops'), 24)])
        self.assertEqual(sorted(self.service.askedSeasons), expected)

    def test_the_pictures_are_stored_for_the_listings(self):
        self._run()
        self.assertEqual(self._store().getStills(['Der Bergdoktor']),
                         {('Der Bergdoktor', 17, 1): 'eins.jpg',
                          ('Der Bergdoktor', 17, 2): 'zwei.jpg',
                          ('Der Bergdoktor', 18, 1): 'eins.jpg',
                          ('Der Bergdoktor', 18, 2): 'zwei.jpg'})

    def test_a_season_of_a_show_the_service_does_not_know_is_not_asked_for(self):
        self.service.known = ['Die Rosenheim-Cops']
        self._run()
        self.assertEqual([job[1] for job in self.service.askedSeasons], [24])

    def test_a_season_asked_about_before_is_not_asked_again(self):
        database = Database()
        self._run(database)
        before = len(self.service.askedSeasons)
        MetadataPrefetch().run(database)
        self.assertEqual(len(self.service.askedSeasons), before)

    def test_a_season_the_service_cannot_answer_stays_open(self):
        # A network failure must not be remembered as "there is nothing".
        self.service.stills = None
        self._run()
        self.assertEqual(self._store().getStills(['Der Bergdoktor']), {})
        self.assertFalse(self._store().episodesKnown('Der Bergdoktor', 18))

    def test_a_second_pass_over_the_same_film_list_reads_nothing(self):
        # Nothing can be missing until a new film list arrives.
        database = Database()
        prefetch = self._run(database)
        prefetch.run(database)
        self.assertEqual(database.asked, 1)

    def test_a_new_film_list_is_gone_through_again(self):
        database = Database()
        prefetch = self._run(database)
        self.settings.setLastUpdate(1757000000)
        database.shownames = SHOWS + ['Doppelhaushälfte']
        prefetch.run(database)
        self.assertEqual(database.asked, 2)
        self.assertIn('Doppelhaushälfte', self.service.asked)

    def test_an_unfinished_pass_carries_on_next_time(self):
        self.addCleanup(setattr, metadataPrefetch, 'PASS_SECONDS',
                        metadataPrefetch.PASS_SECONDS)
        self.addCleanup(setattr, metadataPrefetch, 'THREADS',
                        metadataPrefetch.THREADS)
        metadataPrefetch.PASS_SECONDS = -1
        metadataPrefetch.THREADS = 1
        database = Database()
        prefetch = self._run(database)
        self.assertEqual(self.service.asked, [])
        metadataPrefetch.PASS_SECONDS = 300
        prefetch.run(database)
        self.assertEqual(sorted(self.service.asked), sorted(SHOWS))

    def test_it_says_how_much_it_fetched(self):
        self.assertEqual(MetadataPrefetch().run(Database()), (5, 3))

    def test_it_says_when_there_was_nothing_left_to_fetch(self):
        # A button that answers with nothing at all looks broken, so whoever
        # pressed it has to be able to tell the two apart.
        self._run()
        self.assertEqual(MetadataPrefetch().run(Database()), (0, 0))

    def test_a_run_somebody_watches_reports_how_far_it_has_come(self):
        reported = []
        prefetch = MetadataPrefetch()
        prefetch.run(Database(), progress=lambda *args: reported.append(args))
        self.assertEqual(reported[0], ('shows', 0, 5))
        self.assertIn(('seasons', 0, 3), reported)

    def test_a_run_somebody_watches_is_not_cut_short(self):
        # The five minute limit exists so the service gets back to the film
        # database; nothing waits for that when the user pressed the button.
        self.addCleanup(setattr, metadataPrefetch, 'PASS_SECONDS',
                        metadataPrefetch.PASS_SECONDS)
        metadataPrefetch.PASS_SECONDS = -1
        MetadataPrefetch().run(Database(), progress=lambda *args: None)
        self.assertEqual(sorted(self.service.asked), sorted(SHOWS))

    def test_nothing_is_asked_before_the_first_film_list_has_arrived(self):
        # A fresh installation: there is not even a film table to ask.
        self._context(tmdbEnabled=True, lastUpdate=0)
        database = Database()
        self._run(database)
        self.assertEqual(database.asked, 0)
        self.assertEqual(self.service.asked, [])

    def test_nothing_is_asked_while_the_film_database_is_not_ready(self):
        for status in ('UNINIT', 'UPDATING', 'ABORTED'):
            self._context(tmdbEnabled=True, databaseStatus=status)
            database = Database()
            self._run(database)
            self.assertEqual(self.service.asked, [], status)
            self.assertEqual(database.asked, 0, status)

    def test_nothing_is_asked_while_the_setting_is_off(self):
        self._context(tmdbEnabled=False)
        database = Database()
        self._run(database)
        self.assertEqual(self.service.asked, [])
        self.assertEqual(database.asked, 0, 'not even the film database is read')

    def test_a_service_with_no_token_is_not_asked(self):
        self.service.availableToo = False
        self._run()
        self.assertEqual(self.service.asked, [])

    def test_an_abort_stops_it(self):
        self.monitor.abort = True
        self._run()
        self.assertEqual(self.service.asked, [])

    def test_a_film_database_that_is_not_there(self):
        self._run(database=None)
        self.assertEqual(self.service.asked, [])

    def test_a_show_without_a_name(self):
        self._run(Database(shownames=['', None, 'Der Bergdoktor']))
        self.assertEqual(self.service.asked, ['Der Bergdoktor'])


if __name__ == '__main__':
    unittest.main()
