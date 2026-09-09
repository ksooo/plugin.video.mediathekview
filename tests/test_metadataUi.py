# -*- coding: utf-8 -*-
"""
Tests for what the listings do with metadata from an external service

SPDX-License-Identifier: MIT
"""

import unittest

from tests import support

support.init_app_context()

from resources.lib.ui.filmlistUi import FilmlistUi
from resources.lib.ui.seasonUi import SeasonUi
from resources.lib.ui.showUi import ShowUi

REFRESH = 'Metadaten neu laden'
STRINGS = {30922: 'Als Film herunterladen', 30924: 'Als Episode herunterladen',
           30992: 'Staffel %d', 30995: REFRESH}

POSTER = 'https://image.tmdb.org/t/p/w500/poster.jpg'
FANART = 'https://image.tmdb.org/t/p/w1280/fanart.jpg'
SEASON_POSTER = 'https://image.tmdb.org/t/p/w500/season5.jpg'
STILL = 'https://image.tmdb.org/t/p/w300/erben.jpg'

RECORD = {
    'tmdbid': 41149,
    'poster': POSTER,
    'fanart': FANART,
    'plot': 'Zwei Kommissare in Rosenheim.',
    'genres': ['Krimi'],
    'premiered': '2002-01-01',
    'rating': 6.8,
    'votes': 42,
    'mpaa': 'FSK 12',
    'imdbid': 'tt0367297',
}


class Metadata(object):
    """Stands in for the metadata layer; asks nothing of anybody."""

    def __init__(self, record=RECORD, seasons=None, on=True):
        self.record = record
        self.seasons = seasons or {}
        self.on = on
        self.asked = []

    def enabled(self):
        return self.on

    def forShow(self, showname, mayAsk=False):
        self.asked.append((showname, mayAsk))
        return self.record

    def seasonOf(self, showname, season):
        return self.seasons.get(season)


def _film(title='Erben (S05/E02)', channel='ARD', show='Die Rosenheim-Cops'):
    return ('hash', title, show, channel, 'Worum es geht.', 60, 0, '',
            'https://example.org/a.mp4', '', '')


def _show(name='Die Rosenheim-Cops', channel='ZDF'):
    return ('a1b2c3d4', channel, name, channel)


class FilmArtworkTest(unittest.TestCase):
    """What a film in a show's own listing shows."""

    def setUp(self):
        self.xbmcplugin = support.install_kodi_stubs()
        self.plugin = support.Plugin(strings=STRINGS)

    def _item(self, record=RECORD, stills=None, title='Erben (S05/E02)',
              longTitle=False):
        film = _film(title=title)
        records = {film[2]: record} if record else {}
        ui = FilmlistUi(self.plugin, pLongTitle=longTitle)
        ui.generate([film], pShowMetadata=records, pStills=stills)
        return self.xbmcplugin.items[0][1]

    def _stills(self, show='Die Rosenheim-Cops', season=5, episode=2):
        return {(show, season, episode): STILL}

    def _furnished(self, seasonPosters=None, title='Erben (S05/E02)'):
        """An item with everything the store could know about it."""
        film = _film(title=title)
        ui = FilmlistUi(self.plugin, pLongTitle=False)
        ui.generate([film], pShowMetadata={film[2]: RECORD},
                    pStills=self._stills(), pSeasonPosters=seasonPosters)
        return self.xbmcplugin.items[0][1]

    def test_the_posters_hang_under_their_own_keys(self):
        # Where Kodi keeps them for a library episode, and where the
        # information dialog looks for them - not as `poster`, which a skin
        # would show instead of the episode's own picture.
        item = self._furnished(seasonPosters={('Die Rosenheim-Cops', 5): SEASON_POSTER})
        self.assertEqual(item.art['season.poster'], SEASON_POSTER)
        self.assertEqual(item.art['tvshow.poster'], POSTER)
        self.assertEqual(item.art['thumb'], STILL)
        self.assertNotIn('poster', item.art)

    def test_the_shows_poster_stands_in_for_a_season_without_one(self):
        item = self._furnished()
        self.assertEqual(item.art['tvshow.poster'], POSTER)
        self.assertNotIn('season.poster', item.art)

    def test_the_poster_of_another_season_is_not_taken(self):
        item = self._furnished(seasonPosters={('Die Rosenheim-Cops', 7): SEASON_POSTER})
        self.assertNotIn('season.poster', item.art)

    def test_a_film_that_names_no_season_has_no_season_poster(self):
        item = self._furnished(seasonPosters={('Die Rosenheim-Cops', 5): SEASON_POSTER},
                           title='Ein Sonderfall')
        self.assertNotIn('season.poster', item.art)
        self.assertEqual(item.art['tvshow.poster'], POSTER)

    def test_the_episodes_own_picture_is_the_one_it_wears(self):
        # In the thumb, which is where a skin takes the picture of an
        # episode from - Estuary's ShiftThumbVar, beside the list.
        item = self._item(stills=self._stills())
        self.assertEqual(item.art['thumb'], STILL)
        self.assertEqual(item.art['fanart'], FANART)

    def test_the_show_poster_is_not_put_on_a_film(self):
        # A skin prefers the poster over the episode's own picture wherever
        # one is set, so the show's poster would push it off the screen.
        for stills in (self._stills(), None):
            self.assertNotIn('poster', self._item(stills=stills).art)

    def test_a_film_without_a_picture_of_its_own_shows_the_channel_logo(self):
        item = self._item()
        self.assertTrue(item.art['thumb'].endswith('ard-i.png'), item.art['thumb'])

    def test_a_film_of_another_episode_does_not_take_the_picture(self):
        item = self._item(stills=self._stills(episode=7))
        self.assertTrue(item.art['thumb'].endswith('ard-i.png'), item.art['thumb'])

    def test_a_film_of_another_season_does_not_take_the_picture(self):
        item = self._item(stills=self._stills(season=6))
        self.assertTrue(item.art['thumb'].endswith('ard-i.png'), item.art['thumb'])

    def test_a_film_of_another_show_does_not_take_it_either(self):
        ui = FilmlistUi(self.plugin, pLongTitle=True)
        ui.generate([_film(show='Der Bergdoktor')],
                    pShowMetadata={'Die Rosenheim-Cops': RECORD},
                    pStills=self._stills())
        item = self.xbmcplugin.items[0][1]
        self.assertTrue(item.art['thumb'].endswith('ard-i.png'), item.art['thumb'])

    def test_a_film_that_names_no_episode_has_no_picture_of_its_own(self):
        item = self._item(stills=self._stills(), title='Ein Sonderfall')
        self.assertTrue(item.art['thumb'].endswith('ard-i.png'), item.art['thumb'])

    def test_the_same_belongs_in_a_mixed_listing(self):
        # A search shows films of many shows, and the rule does not change.
        item = self._item(stills=self._stills(), longTitle=True)
        self.assertEqual(item.art['thumb'], STILL)
        self.assertNotIn('poster', item.art)

    def test_the_channel_logo_stays_the_icon(self):
        self.assertTrue(self._item().art['icon'].endswith('ard-i.png'),
                        self._item().art['icon'])

    def test_the_channel_logo_is_all_there_is_without_metadata(self):
        item = self._item(record=None)
        self.assertTrue(item.art['thumb'].endswith('ard-i.png'), item.art['thumb'])
        self.assertTrue(item.art['fanart'].endswith('ard-f.png'), item.art['fanart'])

    def test_the_genre_and_age_rating_of_the_programme_are_taken(self):
        info = self._item().info
        self.assertEqual(info['genre'], ['Krimi'])
        self.assertEqual(info['mpaa'], 'FSK 12')

    def test_a_show_can_be_asked_about_again(self):
        # A wrong poster is stuck otherwise: there is no library dialog to
        # pick the artwork in.
        support.init_app_context(settings=support.Settings(tmdbEnabled=True))
        entries = [entry[0] for entry in self._item().context_menu]
        self.assertIn(REFRESH, entries)

    def test_asking_again_sits_behind_the_downloads(self):
        # The menu is mostly used for downloading, so that comes first.
        support.init_app_context(settings=support.Settings(tmdbEnabled=True))
        entries = [entry[0] for entry in self._item().context_menu]
        self.assertEqual(entries[-1], REFRESH, entries)

    def test_nothing_is_offered_while_the_setting_is_off(self):
        support.init_app_context(settings=support.Settings(tmdbEnabled=False))
        entries = [entry[0] for entry in self._item().context_menu]
        self.assertNotIn(REFRESH, entries)

    def test_a_listing_of_many_shows_does_not_offer_it(self):
        # It would do something invisible: those listings show no metadata.
        support.init_app_context(settings=support.Settings(tmdbEnabled=True))
        ui = FilmlistUi(self.plugin, pLongTitle=True)
        ui.generate([_film()])
        entries = [entry[0] for entry in self.xbmcplugin.items[0][1].context_menu]
        self.assertNotIn(REFRESH, entries)

    def test_the_films_own_words_are_left_alone(self):
        # The film list has a description, a title and a broadcast date for
        # every film. The service knows the programme, not this episode.
        info = self._item().info
        self.assertEqual(info['plot'], 'Worum es geht.')
        self.assertNotIn('rating', info)
        self.assertNotIn('premiered', info)


class SeasonArtworkTest(unittest.TestCase):

    def setUp(self):
        support.install_kodi_stubs()
        self.plugin = support.Plugin(strings=STRINGS)

    def _item(self, metadata):
        items = SeasonUi(self.plugin).generateItems(
            [(5, [_film()])], 'ZDF', 'a1b2c3d4', 'Die Rosenheim-Cops', metadata)
        return items[0][1]

    def test_a_season_of_its_own_wins(self):
        metadata = Metadata(seasons={5: {'poster': SEASON_POSTER, 'plot': 'Staffel 5.'}})
        item = self._item(metadata)
        self.assertEqual(item.art['poster'], SEASON_POSTER)
        self.assertEqual(item.info['plot'], 'Staffel 5.')

    def test_the_programme_stands_in_where_the_season_has_nothing(self):
        item = self._item(Metadata())
        self.assertEqual(item.art['poster'], POSTER)
        self.assertEqual(item.info['plot'], 'Zwei Kommissare in Rosenheim.')

    def test_without_metadata_it_is_the_channel_logo(self):
        item = self._item(None)
        self.assertTrue(item.art['thumb'].endswith('ard-i.png'), item.art['thumb'])
        self.assertNotIn('plot', item.info)


class ShowArtworkTest(unittest.TestCase):
    """A listing of shows reads what is stored and asks nothing.

    A channel can hold 1746 shows, and asking takes about a second each.
    """

    def setUp(self):
        self.xbmcplugin = support.install_kodi_stubs()
        self.plugin = support.Plugin(strings=STRINGS)

    def _item(self, metadata):
        ShowUi(self.plugin).generate([_show()], metadata)
        return self.xbmcplugin.items[0][1]

    def test_it_never_asks(self):
        metadata = Metadata()
        self._item(metadata)
        self.assertEqual(metadata.asked, [('Die Rosenheim-Cops', False)])

    def test_everything_the_service_knows_is_shown(self):
        item = self._item(Metadata())
        self.assertEqual(item.art['poster'], POSTER)
        self.assertEqual(item.art['fanart'], FANART)
        self.assertEqual(item.info['plot'], 'Zwei Kommissare in Rosenheim.')
        self.assertEqual(item.info['genre'], ['Krimi'])
        self.assertEqual(item.info['premiered'], '2002-01-01')
        self.assertEqual(item.info['rating'], 6.8)
        self.assertEqual(item.info['votes'], 42)
        self.assertEqual(item.info['mpaa'], 'FSK 12')

    def test_the_identifier_is_passed_on(self):
        # Whatever else reads the listing can look the show up for itself.
        self.assertEqual(self._item(Metadata()).unique_ids, {'imdb': 'tt0367297'})

    def test_a_show_says_it_is_one(self):
        info = self._item(Metadata()).info
        self.assertEqual(info['mediatype'], 'tvshow')
        self.assertEqual(info['tvshowtitle'], 'Die Rosenheim-Cops')

    def test_a_show_can_be_asked_about_again(self):
        entries = [entry[0] for entry in self._item(Metadata()).context_menu]
        self.assertIn(REFRESH, entries)

    def test_asking_again_sits_behind_the_downloads(self):
        entries = [entry[0] for entry in self._item(Metadata()).context_menu]
        self.assertEqual(entries[-1], REFRESH, entries)

    def test_nothing_is_offered_while_the_setting_is_off(self):
        entries = [entry[0] for entry in self._item(Metadata(on=False)).context_menu]
        self.assertNotIn(REFRESH, entries)

    def test_an_unknown_show_looks_as_it_did(self):
        item = self._item(Metadata(record=None))
        self.assertTrue(item.art['thumb'].endswith('zdf-i.png'), item.art['thumb'])
        self.assertNotIn('plot', item.info)


if __name__ == '__main__':
    unittest.main()
