# -*- coding: utf-8 -*-
"""
Tests for when the store is read and when the service is asked

SPDX-License-Identifier: MIT
"""

import shutil
import tempfile
import unittest

from tests import support

support.init_app_context()

import resources.lib.metadata as metadata
from resources.lib.metadata import Metadata

RECORD = {
    'tmdbid': 14509,
    'poster': 'https://image.tmdb.org/t/p/w500/poster.jpg',
    'fanart': 'https://image.tmdb.org/t/p/w1280/fanart.jpg',
    'plot': 'Eine Klinik in Leipzig.',
    'genres': ['Soap'],
    'premiered': '1998-10-26',
    'rating': 6.3,
    'votes': 7,
    'mpaa': 'FSK 6',
    'imdbid': 'tt0178142',
    'seasons': {1: {'poster': 'https://image.tmdb.org/t/p/w500/s1.jpg', 'plot': None}},
}


class Service(object):
    """Stands in for the TMDB client and records what it was asked."""

    def __init__(self, answer=RECORD, availableToo=True, stills=None):
        self.asked = []
        self.answer = answer
        self.availableToo = availableToo
        self.stills = {1: 'eins.jpg', 2: 'zwei.jpg'} if stills is None else stills

    def available(self):
        return self.availableToo

    def lookupShow(self, showname):
        self.asked.append(showname)
        return self.answer

    def lookupSeason(self, tmdbid, season):
        self.asked.append((tmdbid, season))
        return self.stills


class MetadataTest(unittest.TestCase):

    def setUp(self):
        self.datapath = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.datapath)
        support.init_app_context(settings=support.Settings(
            datapath=self.datapath, tmdbEnabled=True, tmdbToken='eyJtoken'))

    def _metadata(self, service=None):
        data = Metadata()
        self.addCleanup(data.exit)
        data.service = service if service is not None else Service()
        return data

    def test_a_listing_of_many_shows_does_not_ask(self):
        # A channel can hold 1746 shows, and asking takes a second each.
        service = Service()
        self.assertIsNone(self._metadata(service).forShow('Der Bergdoktor'))
        self.assertEqual(service.asked, [])

    def test_a_listing_about_one_show_may_ask(self):
        service = Service()
        record = self._metadata(service).forShow('Der Bergdoktor', mayAsk=True)
        self.assertEqual(record['tmdbid'], 14509)
        self.assertEqual(service.asked, ['Der Bergdoktor'])

    def test_what_was_asked_once_is_not_asked_again(self):
        service = Service()
        data = self._metadata(service)
        data.forShow('Der Bergdoktor', mayAsk=True)
        record = data.forShow('Der Bergdoktor', mayAsk=True)
        self.assertEqual(service.asked, ['Der Bergdoktor'])
        self.assertEqual(record['poster'], RECORD['poster'])

    def test_a_show_asked_about_before_needs_no_asking(self):
        service = Service()
        self._metadata(service).forShow('Der Bergdoktor', mayAsk=True)
        other = Service()
        record = self._metadata(other).forShow('Der Bergdoktor')
        self.assertEqual(record['tmdbid'], 14509)
        self.assertEqual(other.asked, [], 'the store already knew')

    def test_a_show_the_service_does_not_know_is_not_asked_about_twice(self):
        service = Service(answer=None)
        data = self._metadata(service)
        self.assertIsNone(data.forShow('Tagesschau', mayAsk=True))
        self.assertIsNone(data.forShow('Tagesschau', mayAsk=True))
        self.assertEqual(service.asked, ['Tagesschau'])

    def test_the_seasons_are_kept_too(self):
        data = self._metadata()
        data.forShow('Der Bergdoktor', mayAsk=True)
        self.assertEqual(data.seasonOf('Der Bergdoktor', 1)['poster'],
                         RECORD['seasons'][1]['poster'])
        self.assertIsNone(data.seasonOf('Der Bergdoktor', 7))

    def test_nothing_happens_while_the_setting_is_off(self):
        support.init_app_context(settings=support.Settings(
            datapath=self.datapath, tmdbEnabled=False, tmdbToken='eyJtoken'))
        service = Service()
        data = self._metadata(service)
        self.assertIsNone(data.forShow('Der Bergdoktor', mayAsk=True))
        self.assertIsNone(data.seasonOf('Der Bergdoktor', 1))
        self.assertEqual(service.asked, [])

    def test_a_service_with_no_token_is_not_asked(self):
        service = Service(availableToo=False)
        self.assertIsNone(self._metadata(service).forShow('Der Bergdoktor', mayAsk=True))
        self.assertEqual(service.asked, [])

    def test_stored_metadata_survives_the_token_being_removed(self):
        # The switch governs the feature; the token only governs asking.
        self._metadata().forShow('Der Bergdoktor', mayAsk=True)
        support.init_app_context(settings=support.Settings(
            datapath=self.datapath, tmdbEnabled=True, tmdbToken=''))
        data = self._metadata(Service(availableToo=False))
        self.assertEqual(data.forShow('Der Bergdoktor')['tmdbid'], 14509)

    def test_forgetting_a_show_asks_again(self):
        # The cure for a wrong match, and the only one: without a library
        # there is no dialog for the user to choose the artwork in.
        service = Service()
        data = self._metadata(service)
        data.forShow('Die Rosenheim-Cops', mayAsk=True)
        service.answer = dict(RECORD, tmdbid=41149, poster='besser.jpg')
        record = data.forget('Die Rosenheim-Cops')
        self.assertEqual(service.asked, ['Die Rosenheim-Cops'] * 2)
        self.assertEqual(record['poster'], 'besser.jpg')
        self.assertEqual(data.forShow('Die Rosenheim-Cops')['poster'], 'besser.jpg')

    def test_forgetting_a_show_drops_its_seasons_too(self):
        data = self._metadata(Service(answer=RECORD))
        data.forShow('Die Rosenheim-Cops', mayAsk=True)
        self.assertIsNotNone(data.seasonOf('Die Rosenheim-Cops', 1))
        data.service = Service(answer=None)
        data.forget('Die Rosenheim-Cops')
        self.assertIsNone(data.seasonOf('Die Rosenheim-Cops', 1))

    def test_forgetting_leaves_the_other_shows_alone(self):
        data = self._metadata()
        data.forShow('Die Rosenheim-Cops', mayAsk=True)
        data.forShow('Der Bergdoktor', mayAsk=True)
        data.forget('Die Rosenheim-Cops')
        self.assertEqual(data.forShow('Der Bergdoktor')['tmdbid'], 14509)

    def test_discarding_everything(self):
        data = self._metadata()
        data.forShow('Die Rosenheim-Cops', mayAsk=True)
        data.forShow('Der Bergdoktor', mayAsk=True)
        data.discardAll()
        other = Service()
        after = self._metadata(other)
        self.assertIsNone(after.forShow('Die Rosenheim-Cops'))
        self.assertIsNone(after.forShow('Der Bergdoktor'))

    def test_nothing_is_forgotten_while_the_setting_is_off(self):
        data = self._metadata()
        data.forShow('Der Bergdoktor', mayAsk=True)
        support.init_app_context(settings=support.Settings(
            datapath=self.datapath, tmdbEnabled=False, tmdbToken='eyJtoken'))
        self.assertIsNone(self._metadata().forget('Der Bergdoktor'))
        support.init_app_context(settings=support.Settings(
            datapath=self.datapath, tmdbEnabled=True, tmdbToken='eyJtoken'))
        self.assertEqual(self._metadata().forShow('Der Bergdoktor')['tmdbid'], 14509)

    def test_a_mixed_listing_reads_the_store_and_asks_nothing(self):
        service = Service()
        data = self._metadata(service)
        data.forShow('Der Bergdoktor', mayAsk=True)
        records = data.forShows(['Der Bergdoktor', 'Tagesschau'])
        self.assertEqual(list(records), ['Der Bergdoktor'])
        self.assertEqual(records['Der Bergdoktor']['poster'], RECORD['poster'])
        self.assertEqual(service.asked, ['Der Bergdoktor'], 'no asking for a listing')

    def test_a_mixed_listing_reads_the_stored_episode_pictures(self):
        service = Service()
        data = self._metadata(service)
        data.episodesOf('Der Bergdoktor', 1, mayAsk=True)
        other = Service()
        after = self._metadata(other)
        self.assertEqual(after.stillsOf(['Der Bergdoktor', 'Tagesschau']),
                         {('Der Bergdoktor', 1, 1): 'eins.jpg',
                          ('Der Bergdoktor', 1, 2): 'zwei.jpg'})
        self.assertEqual(other.asked, [], 'no asking for a listing')

    def test_no_episode_pictures_while_the_setting_is_off(self):
        data = self._metadata()
        data.episodesOf('Der Bergdoktor', 1, mayAsk=True)
        support.init_app_context(settings=support.Settings(
            datapath=self.datapath, tmdbEnabled=False, tmdbToken='eyJtoken'))
        self.assertEqual(self._metadata().stillsOf(['Der Bergdoktor']), {})

    def test_a_listing_reads_the_stored_season_posters(self):
        service = Service()
        data = self._metadata(service)
        data.forShow('Der Bergdoktor', mayAsk=True)
        self.assertEqual(data.seasonsOf(['Der Bergdoktor']),
                         {('Der Bergdoktor', 1): RECORD['seasons'][1]['poster']})
        self.assertEqual(service.asked, ['Der Bergdoktor'], 'no asking for a listing')

    def test_no_season_posters_while_the_setting_is_off(self):
        data = self._metadata()
        data.forShow('Der Bergdoktor', mayAsk=True)
        support.init_app_context(settings=support.Settings(
            datapath=self.datapath, tmdbEnabled=False, tmdbToken='eyJtoken'))
        self.assertEqual(self._metadata().seasonsOf(['Der Bergdoktor']), {})

    def test_a_mixed_listing_gets_nothing_while_the_setting_is_off(self):
        self._metadata().forShow('Der Bergdoktor', mayAsk=True)
        support.init_app_context(settings=support.Settings(
            datapath=self.datapath, tmdbEnabled=False, tmdbToken='eyJtoken'))
        self.assertEqual(self._metadata().forShows(['Der Bergdoktor']), {})

    def test_the_episodes_of_a_season_may_be_asked_for(self):
        service = Service()
        stills = self._metadata(service).episodesOf('Der Bergdoktor', 1, mayAsk=True)
        self.assertEqual(stills, {1: 'eins.jpg', 2: 'zwei.jpg'})
        self.assertEqual(service.asked, ['Der Bergdoktor', (14509, 1)])

    def test_a_listing_that_may_not_ask_gets_what_is_stored(self):
        service = Service()
        data = self._metadata(service)
        data.episodesOf('Der Bergdoktor', 1, mayAsk=True)
        other = Service()
        after = self._metadata(other)
        self.assertEqual(after.episodesOf('Der Bergdoktor', 1), {1: 'eins.jpg', 2: 'zwei.jpg'})
        self.assertEqual(other.asked, [], 'the store already knew')

    def test_a_season_is_asked_about_once(self):
        service = Service()
        data = self._metadata(service)
        data.episodesOf('Der Bergdoktor', 1, mayAsk=True)
        data.episodesOf('Der Bergdoktor', 1, mayAsk=True)
        self.assertEqual(service.asked, ['Der Bergdoktor', (14509, 1)])

    def test_a_season_whose_episodes_have_no_pictures_is_not_asked_about_twice(self):
        service = Service(stills={})
        data = self._metadata(service)
        self.assertEqual(data.episodesOf('In aller Freundschaft', 1, mayAsk=True), {})
        self.assertEqual(data.episodesOf('In aller Freundschaft', 1, mayAsk=True), {})
        self.assertEqual(service.asked, ['In aller Freundschaft', (14509, 1)])

    def test_a_show_the_service_does_not_know_has_no_episodes_either(self):
        service = Service(answer=None)
        self.assertEqual(
            self._metadata(service).episodesOf('Tagesschau', 1, mayAsk=True), {})

    def test_a_listing_of_no_particular_season_asks_nothing(self):
        service = Service()
        self.assertEqual(
            self._metadata(service).episodesOf('Der Bergdoktor', None, mayAsk=True), {})
        self.assertEqual(service.asked, [])

    def test_no_episodes_while_the_setting_is_off(self):
        support.init_app_context(settings=support.Settings(
            datapath=self.datapath, tmdbEnabled=False, tmdbToken='eyJtoken'))
        service = Service()
        self.assertEqual(
            self._metadata(service).episodesOf('Der Bergdoktor', 1, mayAsk=True), {})
        self.assertEqual(service.asked, [])

    def test_a_failed_season_request_is_not_taken_for_an_answer(self):
        service = Service()
        service.stills = None
        data = self._metadata(service)
        self.assertEqual(data.episodesOf('Der Bergdoktor', 1, mayAsk=True), {})
        service.stills = {1: 'eins.jpg'}
        self.assertEqual(data.episodesOf('Der Bergdoktor', 1, mayAsk=True),
                         {1: 'eins.jpg'})

    def test_a_show_without_a_name(self):
        service = Service()
        self.assertIsNone(self._metadata(service).forShow('', mayAsk=True))
        self.assertEqual(service.asked, [])


if __name__ == '__main__':
    unittest.main()
