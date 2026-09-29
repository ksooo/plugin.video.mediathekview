# -*- coding: utf-8 -*-
"""
Tests for opening a listing and selecting a film in it

SPDX-License-Identifier: MIT
"""

import unittest

from tests import support

support.init_app_context()

import resources.lib.ui.jump as jump
from resources.lib.ui.jump import Jump

SHOW_URL = 'plugin://plugin.video.mediathekview.ksooo/?mode=films&show=1c6953ff'
URL = SHOW_URL + '&season=5'
VIEW = 55


class Container(object):
    """Stands in for the listing on screen.

    ``appears`` is how many polls it takes before a listing is there, which
    is what waiting for the plugin to fill it looks like from outside.
    """

    def __init__(self, films=('a', 'b', 'c'), appears=0, abort=False):
        self.films = list(films)
        self.appears = appears
        self.abort = abort
        self.activated = []
        self.selected = []
        self.waits = 0
        self.polls = 0

    def activate(self, url):
        self.activated.append(url)
        self.polls = 0

    def path(self):
        self.polls += 1
        if not self.activated or self.polls <= self.appears:
            return 'plugin://other/'
        return self.activated[-1]

    def loading(self):
        return False

    def viewId(self):
        return VIEW

    def count(self, viewId):
        return len(self.films)

    def filmId(self, viewId, index):
        return self.films[index]

    def select(self, viewId, index):
        self.selected.append((viewId, index))

    def waited(self, seconds):
        self.waits += 1
        return self.abort


class JumpTest(unittest.TestCase):

    def test_it_opens_the_listing_and_selects_the_film(self):
        container = Container()
        self.assertTrue(Jump(container).toFilm([URL], 'b'))
        self.assertEqual(container.activated, [URL])
        self.assertEqual(container.selected, [(VIEW, 1)])

    def test_it_waits_for_the_listing_to_appear(self):
        # The plugin that fills it is a script of its own, and only once it
        # has run does the film exist to be selected.
        container = Container(appears=3)
        self.assertTrue(Jump(container).toFilm([URL], 'c'))
        self.assertEqual(container.selected, [(VIEW, 2)])
        self.assertGreater(container.waits, 3)

    def test_the_position_is_the_one_on_screen(self):
        # Kodi sorts the listing itself, so what the query returned says
        # nothing about where the film ended up.
        container = Container(films=('c', 'a', 'b'))
        Jump(container).toFilm([URL], 'a')
        self.assertEqual(container.selected, [(VIEW, 1)])

    def test_a_film_that_is_not_in_the_listing_selects_nothing(self):
        # A filter can hide it; the cursor then stays where Kodi put it.
        container = Container()
        self.assertFalse(Jump(container).toFilm([URL], 'nowhere'))
        self.assertEqual(container.selected, [])

    def test_it_walks_through_the_show_on_the_way_to_a_season(self):
        # Kodi's ".." walks the listings that were shown, so the show has to
        # be one of them for ".." to lead to its seasons.
        container = Container()
        self.assertTrue(Jump(container).toFilm([SHOW_URL, URL], 'b'))
        self.assertEqual(container.activated, [SHOW_URL, URL])
        self.assertEqual(container.selected, [(VIEW, 1)])

    def test_a_show_that_never_comes_stops_it_there(self):
        self.addCleanup(setattr, jump, 'WAIT_SECONDS', jump.WAIT_SECONDS)
        jump.WAIT_SECONDS = 0.2
        container = Container(appears=10 ** 6)
        self.assertFalse(Jump(container).toFilm([SHOW_URL, URL], 'a'))
        self.assertEqual(container.activated, [SHOW_URL])

    def test_a_listing_that_never_comes(self):
        self.addCleanup(setattr, jump, 'WAIT_SECONDS', jump.WAIT_SECONDS)
        jump.WAIT_SECONDS = 0.2
        container = Container(appears=10 ** 6)
        self.assertFalse(Jump(container).toFilm([URL], 'a'))
        self.assertEqual(container.selected, [])

    def test_kodi_shutting_down_stops_it(self):
        container = Container(abort=True)
        self.assertFalse(Jump(container).toFilm([URL], 'a'))
        self.assertEqual(container.selected, [])


if __name__ == '__main__':
    unittest.main()
