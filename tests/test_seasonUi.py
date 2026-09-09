# -*- coding: utf-8 -*-
"""
Tests for the season folders in front of a show's films

SPDX-License-Identifier: MIT
"""

import unittest

from tests import support

support.init_app_context()

from resources.lib.ui.filmlistUi import FilmlistUi
from resources.lib.ui.seasonUi import SeasonUi

SEASON = 30992


def _row(title, channel='ARD'):
    return ('hash', title, 'Sendung', channel, '', 60, 0, '',
            'https://example.org/a.mp4', '', '')


class SeasonItemTest(unittest.TestCase):

    def setUp(self):
        support.install_kodi_stubs()
        self.plugin = support.Plugin(strings={SEASON: 'Staffel %d'})

    def _items(self, seasons, channel='ARD', show='a1b2c3d4',
               showname='Doppelhaushälfte'):
        # The url needs the show id, everything else the show name - they
        # used to be the same argument, which put an md5 fragment into
        # tvshowtitle.
        return SeasonUi(self.plugin).generateItems(seasons, channel, show, showname)

    def test_one_folder_per_season(self):
        items = self._items([(5, [_row('Erben (S05/E02)')]),
                             (6, [_row('Ufo (S06/E07)')])])
        self.assertEqual([item[1].label for item in items],
                         ['Staffel 5', 'Staffel 6'])
        self.assertTrue(all(item[2] for item in items), 'seasons are folders')

    def test_a_season_says_what_it_is(self):
        (_, item, _) = self._items([(5, [_row('Erben (S05/E02)')])])[0]
        self.assertEqual(item.info['season'], 5)
        self.assertEqual(item.info['mediatype'], 'season')
        self.assertEqual(item.info['tvshowtitle'], 'Doppelhaushälfte')

    def test_a_season_leads_back_into_the_same_show(self):
        (url, _, _) = self._items([(5, [_row('Erben (S05/E02)')])])[0]
        self.assertIn('mode=films', url)
        self.assertIn('season=5', url)
        self.assertIn('show=a1b2c3d4', url)

    def test_a_show_without_a_channel_of_its_own_still_leads_somewhere(self):
        # Shows can be grouped across channels, and then there is none.
        (url, _, _) = self._items([(5, [_row('Erben (S05/E02)')])], channel='')[0]
        self.assertIn('channel=0', url)

    def test_the_icon_comes_from_the_films_channel(self):
        (_, item, _) = self._items([(5, [_row('Erben (S05/E02)', channel='ZDF')])])[0]
        self.assertTrue(item.art['icon'].endswith('zdf-i.png'), item.art['icon'])
        self.assertTrue(item.art['fanart'].endswith('zdf-f.png'), item.art['fanart'])


class SeasonsAndFilmsTogetherTest(unittest.TestCase):
    """A show with seasons still has films that name none.

    They share the listing rather than going into a folder of their own -
    Kodi puts the folders first by itself.
    """

    def setUp(self):
        self.xbmcplugin = support.install_kodi_stubs()
        self.plugin = support.Plugin(strings={SEASON: 'Staffel %d'})

    def test_the_seasons_come_before_the_films(self):
        seasons = SeasonUi(self.plugin).generateItems(
            [(5, [_row('Erben (S05/E02)')])], 'ARD', 'a1b2c3d4', 'Sendung')
        FilmlistUi(self.plugin, pLongTitle=False).generate(
            [_row('Making of')], seasons)
        labels = [item[1].label for item in self.xbmcplugin.items]
        self.assertEqual(labels, ['Staffel 5', 'Making of'])
        self.assertEqual([item[2] for item in self.xbmcplugin.items], [True, False])

    def test_a_listing_without_seasons_is_what_it_was(self):
        FilmlistUi(self.plugin, pLongTitle=False).generate([_row('Making of')])
        self.assertEqual([item[1].label for item in self.xbmcplugin.items],
                         ['Making of'])


if __name__ == '__main__':
    unittest.main()
