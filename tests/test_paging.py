# -*- coding: utf-8 -*-
"""
Tests for cutting a listing into pages

SPDX-License-Identifier: MIT
"""

import unittest

from tests import support

support.init_app_context()

from resources.lib.paging import page, pageOf
from resources.lib.plugin import MediathekViewPlugin
import resources.lib.ui.filmlistUi as FilmlistUi

ROWS = list(range(10))


class PageTest(unittest.TestCase):

    def test_the_first_page_and_the_way_on(self):
        self.assertEqual(page(ROWS, 0, 4), ([0, 1, 2, 3], 4))

    def test_a_page_in_the_middle(self):
        self.assertEqual(page(ROWS, 4, 4), ([4, 5, 6, 7], 8))

    def test_the_last_page_leads_nowhere(self):
        self.assertEqual(page(ROWS, 8, 4), ([8, 9], None))

    def test_a_listing_that_fits_on_one_page(self):
        self.assertEqual(page(ROWS, 0, 10), (ROWS, None))
        self.assertEqual(page(ROWS, 0, 100), (ROWS, None))

    def test_no_page_size_is_no_paging(self):
        self.assertEqual(page(ROWS, 0, 0), (ROWS, None))

    def test_an_offset_past_the_end(self):
        self.assertEqual(page(ROWS, 20, 4), ([], None))

    def test_an_offset_of_nonsense(self):
        self.assertEqual(page(ROWS, -5, 4), ([0, 1, 2, 3], 4))

    def test_nothing_to_page(self):
        self.assertEqual(page([], 0, 4), ([], None))


class PageOfTest(unittest.TestCase):
    """Which page a film is on, which is what a jump to it needs."""

    def test_the_page_a_row_is_on(self):
        self.assertEqual(pageOf(0, 4), 0)
        self.assertEqual(pageOf(3, 4), 0)
        self.assertEqual(pageOf(4, 4), 4)
        self.assertEqual(pageOf(9, 4), 8)

    def test_without_paging_everything_is_on_the_first(self):
        self.assertEqual(pageOf(9, 0), 0)



class _Metadata(object):

    def forShows(self, shownames):
        return {}

    def stillsOf(self, shownames):
        return {}

    def seasonsOf(self, shownames):
        return {}


class Plugin(support.Plugin):
    """The part of the plugin that decides which films a page lists."""

    _generateFilms = MediathekViewPlugin._generateFilms
    _fill = MediathekViewPlugin._fill
    _page = MediathekViewPlugin._page
    _offset = MediathekViewPlugin._offset
    _nextPage = MediathekViewPlugin._nextPage
    _withoutDuplicates = MediathekViewPlugin._withoutDuplicates

    def __init__(self, offset=None, pageSize=4, hideAudioDescription=False):
        super(Plugin, self).__init__()
        self.args = {} if offset is None else {'offset': str(offset)}
        self.settings = support.Settings(
            pageSize=pageSize, hideAudioDescription=hideAudioDescription)
        self.metadata = _Metadata()

    def get_arg(self, argname, default):
        return self.args.get(argname, default)


class ListingPagesTest(unittest.TestCase):

    PARAMS = {'mode': 'research', 'search': 'Tatort'}

    def setUp(self):
        self.listed = []
        original = FilmlistUi.FilmlistUi.generate

        def generate(ui, films, *args, **kwargs):
            self.listed.append((films, kwargs.get('pNextPage')))

        FilmlistUi.FilmlistUi.generate = generate
        self.addCleanup(setattr, FilmlistUi.FilmlistUi, 'generate', original)

    def _films(self, titles, offset=None, hideAudioDescription=False):
        asked = []
        rows = [(index, title, 'Sendung', 'ARD') for (index, title) in enumerate(titles)]

        def fetch(offset, limit):
            asked.append((offset, limit))
            return rows[offset:offset + limit]

        Plugin(offset, hideAudioDescription=hideAudioDescription)._generateFilms(
            fetch, self.PARAMS)
        return (asked, self.listed[0][0], self.listed[0][1])

    def _titles(self, count):
        return ['Film %d' % index for index in range(count)]

    def test_asks_for_one_film_beyond_the_page(self):
        (asked, _, _) = self._films([], offset=8)
        self.assertEqual(asked, [(8, 5)])

    def test_the_first_page_without_an_offset(self):
        (asked, _, _) = self._films([])
        self.assertEqual(asked, [(0, 5)])

    def test_the_film_beyond_the_page_leads_on(self):
        (_, films, nextPage) = self._films(self._titles(9), offset=4)
        self.assertEqual([film[0] for film in films], [4, 5, 6, 7])
        self.assertEqual(nextPage, 'plugin://test/?mode=research&offset=8&search=Tatort')

    def test_a_page_with_nothing_beyond_it_leads_nowhere(self):
        (_, films, nextPage) = self._films(self._titles(4))
        self.assertEqual(len(films), 4)
        self.assertIsNone(nextPage)

    def test_a_page_the_filters_thinned_is_filled_from_further_on(self):
        (_, films, nextPage) = self._films(
            ['A', 'A - Audiodeskription', 'B', 'C', 'D', 'E'],
            hideAudioDescription=True)
        self.assertEqual([film[1] for film in films], ['A', 'B', 'C', 'D'])
        self.assertEqual(nextPage, 'plugin://test/?mode=research&offset=5&search=Tatort')

    def test_the_next_page_starts_past_the_films_dropped(self):
        # Read again on the next page, the twin that dropped it is not there.
        (_, films, nextPage) = self._films(
            ['A', 'B', 'C', 'D', 'D - Audiodeskription', 'E'],
            hideAudioDescription=True)
        self.assertEqual([film[1] for film in films], ['A', 'B', 'C', 'D'])
        self.assertEqual(nextPage, 'plugin://test/?mode=research&offset=5&search=Tatort')

    def test_what_the_filters_left_of_the_last_page_leads_nowhere(self):
        (_, films, nextPage) = self._films(
            ['A', 'A - Audiodeskription', 'B', 'C', 'D'],
            hideAudioDescription=True)
        self.assertEqual(len(films), 4)
        self.assertIsNone(nextPage)

    def test_a_show_listing_is_cut_after_the_query(self):
        (films, nextPage) = Plugin(offset=4)._page(list(range(10)), self.PARAMS)
        self.assertEqual(films, [4, 5, 6, 7])
        self.assertEqual(nextPage, 'plugin://test/?mode=research&offset=8&search=Tatort')


if __name__ == '__main__':
    unittest.main()
