# -*- coding: utf-8 -*-
"""
Tests for what a list item is told about a video

SPDX-License-Identifier: MIT
"""

import unittest

from tests import support

support.init_app_context()

import resources.lib.ui.videoInfo as videoInfo


class VideoInfoTest(unittest.TestCase):

    def setUp(self):
        support.install_kodi_stubs()
        self.item = support.ListItem()

    def _apply(self, **info):
        videoInfo.apply(self.item, info)
        return self.item.info

    def test_the_text_of_a_film(self):
        info = self._apply(title='Erben', sorttitle='erben', plot='Worum es geht.',
                           tvshowtitle='Die Rosenheim-Cops', mpaa='FSK 12',
                           mediatype='episode')
        self.assertEqual(info['title'], 'Erben')
        self.assertEqual(info['tvshowtitle'], 'Die Rosenheim-Cops')
        self.assertEqual(info['mediatype'], 'episode')

    def test_the_numbers_of_an_episode(self):
        info = self._apply(season=5, episode=2, duration=2700)
        self.assertEqual((info['season'], info['episode'], info['duration']),
                         (5, 2, 2700))

    def test_a_single_genre_is_a_list_all_the_same(self):
        # setGenres and setStudios take a list where setInfo took either.
        self.assertEqual(self._apply(studio='ZDF')['studio'], ['ZDF'])
        self.assertEqual(self._apply(genre=['Krimi'])['genre'], ['Krimi'])

    def test_a_rating_carries_its_votes(self):
        info = self._apply(rating=6.8, votes=42)
        self.assertEqual((info['rating'], info['votes']), (6.8, 42))

    def test_a_rating_without_votes(self):
        self.assertEqual(self._apply(rating=6.8)['votes'], 0)

    def test_the_date_belongs_to_the_item_not_to_the_tag(self):
        # It is what sorting by date reads, and Kodi takes a W3C date there.
        self.assertEqual(self._apply(date='2024-07-01T00:30:00')['date'],
                         '2024-07-01T00:30:00')

    def test_a_field_nobody_knows_is_refused(self):
        # setInfo swallowed those, so a typo went unnoticed.
        with self.assertRaises(ValueError):
            self._apply(tvshowtitel='Die Rosenheim-Cops')

    def test_nothing_at_all(self):
        self.assertEqual(self._apply(), {})


if __name__ == '__main__':
    unittest.main()
