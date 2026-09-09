# -*- coding: utf-8 -*-
"""
Tests for what themoviedb.org is asked and what is believed of the answer

SPDX-License-Identifier: MIT
"""

import io
import json
import os
import unittest

from tests import support

support.init_app_context()

import resources.lib.appContext as appContext
import resources.lib.tmdb as tmdb
from resources.lib.tmdb import Tmdb, matches, pick

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')
TOKEN = 'eyJhbGciOiJIUzI1NiJ9.notarealtoken.signature'


def _fixture(name):
    with open(os.path.join(FIXTURES, name), encoding='utf-8') as handle:
        return handle.read()


class MatchTest(unittest.TestCase):
    """Which of their names may stand for one of ours.

    Every case here was taken from a run over all 358 shows the film list
    calls a series, not made up. The rule accepts 234 of them; the ones it
    turns down are mostly a different show with a similar name.
    """

    def test_the_same_name(self):
        self.assertEqual(matches('Der Bergdoktor', 'Der Bergdoktor'), 'equal')

    def test_a_different_separator(self):
        self.assertEqual(matches('Die Heiland - Wir sind Anwalt',
                                 'Die Heiland: Wir sind Anwalt'), 'equal')

    def test_a_hyphen_where_a_space_is(self):
        self.assertEqual(matches('Sketch-History', 'Sketch History'), 'equal')
        self.assertEqual(matches('Azubi Storys', 'Azubi-Storys'), 'equal')

    def test_a_trailing_ellipsis(self):
        self.assertEqual(matches('Kreuzer trifft ...', 'Kreuzer trifft'), 'equal')
        self.assertEqual(matches('Johann König findet:', 'Johann König findet: ...'),
                         'equal')

    def test_an_en_dash_for_a_hyphen(self):
        self.assertEqual(matches('ZDFinfo - die Einzeldokus',
                                 'ZDFinfo – die Einzeldokus'), 'equal')

    def test_their_name_carries_ours_after_a_separator(self):
        self.assertEqual(matches('Morden im Norden',
                                 'Heiter bis tödlich - Morden im Norden'), 'suffix')

    def test_their_name_carries_ours_before_a_separator(self):
        self.assertEqual(matches('Aufgedeckt', 'Aufgedeckt - Rätsel der Geschichte'),
                         'prefix')

    def test_a_word_glued_on_is_not_the_same_show(self):
        # Bolzplatz and Bolzplatz-Duell are two different programmes.
        self.assertIsNone(matches('Bolzplatz', 'Bolzplatz-Duell'))

    def test_a_number_glued_on_is_not_the_same_show(self):
        self.assertIsNone(matches("Ku'damm", "Ku'damm 77"))

    def test_a_missing_article_is_not_enough(self):
        # Deliberately turned down: the same leniency would accept
        # "Ermittler!" as "Der Ermittler", which is a different programme.
        self.assertIsNone(matches('Taunuskrimi', 'Der Taunuskrimi'))
        self.assertIsNone(matches('Ermittler!', 'Der Ermittler'))

    def test_one_word_in_common_is_not_enough(self):
        for (ours, theirs) in (('Seaside Hotel', 'Hotel Bordemer'),
                               ('Bundesliga - 2024/25',
                                'Tradition & Träume: Die 2. Bundesliga 2024/25'),
                               ('Feuer & Flamme', 'Frieda - Mit Feuer und Flamme'),
                               ('Land & lecker', 'Lecker aufs Land - eine Reise'),
                               ('Hubert und Staller', 'Hubert ohne Staller')):
            self.assertIsNone(matches(ours, theirs), '%s / %s' % (ours, theirs))


class PickTest(unittest.TestCase):

    def _results(self, *names):
        return [{'id': index, 'name': name} for (index, name) in enumerate(names)]

    def test_takes_the_first_that_fits(self):
        # The first result is often a different show whose name merely
        # contains ours; looking at three finds six more over the whole list.
        found = pick('Ermittler!', self._results('Der Ermittler', 'Ermittler!'))
        self.assertEqual(found['name'], 'Ermittler!')

    def test_looks_no_further_than_the_third(self):
        results = self._results('eins', 'zwei', 'drei', 'Der Bergdoktor')
        self.assertIsNone(pick('Der Bergdoktor', results))

    def test_nothing_fits(self):
        self.assertIsNone(pick('Tagesschau', self._results('Tagesschau 2000')))

    def test_no_results_at_all(self):
        self.assertIsNone(pick('Tagesschau', []))
        self.assertIsNone(pick('Tagesschau', None))


class LookupTest(unittest.TestCase):
    """A show looked up against the answers the service really gave."""

    def setUp(self):
        support.init_app_context(settings=support.Settings(
            tmdbEnabled=True, tmdbToken=TOKEN))
        self.asked = []
        self.answers = [_fixture('tmdb-search.json'), _fixture('tmdb-show.json')]
        self.addCleanup(setattr, tmdb, 'urlopen', tmdb.urlopen)
        tmdb.urlopen = self._urlopen

    def _urlopen(self, request, timeout=None):
        self.asked.append(request)
        return io.BytesIO(self.answers.pop(0).encode('utf-8'))

    def _lookup(self, name='In aller Freundschaft'):
        return Tmdb().lookupShow(name)

    def test_it_finds_the_show(self):
        record = self._lookup()
        self.assertEqual(record['tmdbid'], 14509)
        self.assertEqual(record['premiered'], '1998-10-26')
        self.assertEqual(record['genres'], ['Soap'])
        self.assertEqual(record['imdbid'], 'tt0178142')

    def test_the_artwork_is_a_url_ready_to_use(self):
        record = self._lookup()
        self.assertTrue(record['poster'].startswith('https://image.tmdb.org/t/p/'), record['poster'])
        self.assertTrue(record['poster'].endswith('.jpg'), record['poster'])
        self.assertIn('/w1280', record['fanart'])

    def test_the_plot_comes_in_german(self):
        self.assertIn('Sachsenklinik', self._lookup()['plot'])

    def test_the_age_rating_is_named_as_one(self):
        # The service says "6" for Germany, which alone means nothing.
        self.assertEqual(self._lookup()['mpaa'], 'FSK 6')

    def test_the_season_posters_come_along(self):
        # They are part of the show's own answer, so no request of their own.
        seasons = self._lookup()['seasons']
        self.assertEqual(len(self.asked), 2)
        self.assertTrue(seasons)
        self.assertIn('image.tmdb.org', seasons[1]['poster'])

    def test_a_season_with_no_artwork_is_not_kept(self):
        self.assertNotIn(29, self._lookup()['seasons'])

    def test_the_language_is_asked_for(self):
        self._lookup()
        self.assertIn('language=de-DE', self.asked[0].full_url)

    def test_a_read_access_token_stays_out_of_the_url(self):
        # Whoever pastes a debug log would otherwise paste their token too.
        self._lookup()
        for request in self.asked:
            self.assertNotIn(TOKEN, request.full_url)
            self.assertEqual(request.get_header('Authorization'), 'Bearer ' + TOKEN)

    def test_an_older_key_has_nowhere_to_go_but_the_url(self):
        support.init_app_context(settings=support.Settings(
            tmdbEnabled=True, tmdbToken='0123456789abcdef'))
        self._lookup()
        self.assertIn('api_key=0123456789abcdef', self.asked[0].full_url)
        self.assertIsNone(self.asked[0].get_header('Authorization'))

    def test_a_show_the_service_does_not_know(self):
        self.answers = ['{"results": []}']
        self.assertIsNone(self._lookup('Tagesschau'))

    def test_a_show_whose_name_does_not_fit(self):
        self.answers = [json.dumps({'results': [{'id': 1, 'name': 'Hotel Bordemer'}]})]
        self.assertIsNone(self._lookup('Seaside Hotel'))
        self.assertEqual(len(self.asked), 1, 'no point asking for the details')


class SeasonLookupTest(unittest.TestCase):
    """The episodes of one season, against the answer the service gave."""

    def setUp(self):
        support.init_app_context(settings=support.Settings(
            tmdbEnabled=True, tmdbToken=TOKEN))
        self.asked = []
        self.answer = _fixture('tmdb-season.json')
        self.addCleanup(setattr, tmdb, 'urlopen', tmdb.urlopen)
        tmdb.urlopen = self._urlopen

    def _urlopen(self, request, timeout=None):
        self.asked.append(request)
        return io.BytesIO(self.answer.encode('utf-8'))

    def test_one_request_brings_the_whole_season(self):
        stills = Tmdb().lookupSeason(41149, 24)
        self.assertEqual(len(self.asked), 1)
        self.assertIn('/tv/41149/season/24', self.asked[0].full_url)
        self.assertEqual(sorted(stills), [1, 2, 3])

    def test_a_still_is_a_url_ready_to_use(self):
        still = Tmdb().lookupSeason(41149, 24)[1]
        self.assertTrue(still.startswith('https://image.tmdb.org/t/p/w300/'), still)
        self.assertTrue(still.endswith('.jpg'), still)

    def test_an_episode_without_a_picture_is_left_out(self):
        self.answer = json.dumps({'episodes': [
            {'episode_number': 1, 'still_path': '/eins.jpg'},
            {'episode_number': 2, 'still_path': None}]})
        self.assertEqual(list(Tmdb().lookupSeason(41149, 24)), [1])

    def test_a_season_where_none_of_the_episodes_has_one(self):
        # In aller Freundschaft has no still for any of its 42 episodes,
        # which is an answer and not a failure.
        self.answer = json.dumps({'episodes': [{'episode_number': 1}]})
        self.assertEqual(Tmdb().lookupSeason(14509, 1), {})

    def test_a_season_the_service_does_not_have_is_an_answer(self):
        # The film list names seasons TMDB has never heard of - Terra X has a
        # season 2018 - and those must not be asked about again and again.
        def urlopen(request, timeout=None):
            raise tmdb.HTTPError(request.full_url, 404, 'Not Found', {}, None)
        tmdb.urlopen = urlopen
        self.assertEqual(Tmdb().lookupSeason(41149, 2018), {})

    def test_a_season_that_could_not_be_asked_for_is_no_answer(self):
        def urlopen(request, timeout=None):
            raise tmdb.URLError('no route to host')
        tmdb.urlopen = urlopen
        self.assertIsNone(Tmdb().lookupSeason(41149, 24))

    def test_a_show_is_not_invented_out_of_a_404(self):
        # Only the season lookup treats "no such thing" as an answer.
        def urlopen(request, timeout=None):
            raise tmdb.HTTPError(request.full_url, 404, 'Not Found', {}, None)
        tmdb.urlopen = urlopen
        self.assertIsNone(Tmdb().lookupShow('Der Bergdoktor'))


class FailureTest(unittest.TestCase):
    """The service is somebody else's, and a listing must not depend on it."""

    def setUp(self):
        support.init_app_context(settings=support.Settings(
            tmdbEnabled=True, tmdbToken=TOKEN))
        self.addCleanup(setattr, tmdb, 'urlopen', tmdb.urlopen)

    def _failing(self, error):
        def urlopen(request, timeout=None):
            raise error
        tmdb.urlopen = urlopen

    def test_a_network_failure_is_no_answer_and_no_exception(self):
        self._failing(tmdb.URLError('no route to host'))
        self.assertIsNone(Tmdb().lookupShow('Der Bergdoktor'))
        logged = [text for (level, text) in appContext.MVLOGGER.messages
                  if level == 'error']
        self.assertTrue(any('no route to host' in text for text in logged), logged)

    def test_an_unusable_answer_is_no_answer_and_no_exception(self):
        tmdb.urlopen = lambda request, timeout=None: io.BytesIO(b'<html>go away</html>')
        self.assertIsNone(Tmdb().lookupShow('Der Bergdoktor'))
        logged = [text for (level, text) in appContext.MVLOGGER.messages
                  if level == 'error']
        self.assertTrue(logged, 'the reason has to reach the log')


class AvailableTest(unittest.TestCase):

    def _available(self, **settings):
        support.init_app_context(settings=support.Settings(**settings))
        return Tmdb().available()

    def test_switched_on_with_a_token(self):
        self.assertTrue(self._available(tmdbEnabled=True, tmdbToken=TOKEN))

    def test_switched_off(self):
        self.assertFalse(self._available(tmdbEnabled=False, tmdbToken=TOKEN))

    def test_no_token_is_as_good_as_switched_off(self):
        self.assertFalse(self._available(tmdbEnabled=True, tmdbToken=''))


if __name__ == '__main__':
    unittest.main()
