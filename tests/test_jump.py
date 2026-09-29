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

URL = 'plugin://plugin.video.mediathekview.ksooo/?mode=films&show=1c6953ff&season=5'
VIEW = 55


class Container(object):
    """Stands in for the listing on screen.

    Kodi sets the path of a listing when the window opens and fetches the
    items afterwards, so this keeps the two apart: ``appears`` is how many
    polls the path takes, ``fills`` how many more the items take, and
    ``swallows`` names the activations that are lost to a listing which was
    still being fetched - which is what a slow machine does to a jump.
    """

    def __init__(self, films=('a', 'b', 'c'), appears=0, abort=False,
                 fills=0, swallows=()):
        self.films = list(films)
        self.appears = appears
        self.fills = fills
        self.swallows = set(swallows)
        self.abort = abort
        self.activated = []
        self.selected = []
        self.waits = 0
        self.polls = 0
        self.shown = None

    def activate(self, url):
        self.activated.append(url)
        self.polls = 0
        if len(self.activated) - 1 in self.swallows:
            # The listing that was still loading arrives and wins.
            return
        self.shown = url

    def path(self):
        self.polls += 1
        if self.shown is None or self.polls <= self.appears:
            return 'plugin://other/'
        return self.shown

    def loading(self):
        return False

    def viewId(self):
        return VIEW

    def count(self, viewId):
        return len(self.films) if self.polls > self.appears + self.fills else 0

    def filmId(self, viewId, index):
        return self.films[index] if self.polls > self.appears + self.fills else ''

    def select(self, viewId, index):
        self.selected.append((viewId, index))

    def waited(self, seconds):
        self.waits += 1
        return self.abort


class JumpTest(unittest.TestCase):

    def test_it_opens_the_listing_and_selects_the_film(self):
        container = Container()
        self.assertTrue(Jump(container).toFilm(URL, 'b'))
        self.assertEqual(container.activated, [URL])
        self.assertEqual(container.selected, [(VIEW, 1)])

    def test_it_waits_for_the_listing_to_appear(self):
        # The plugin that fills it is a script of its own, and only once it
        # has run does the film exist to be selected.
        container = Container(appears=3)
        self.assertTrue(Jump(container).toFilm(URL, 'c'))
        self.assertEqual(container.selected, [(VIEW, 2)])
        self.assertGreater(container.waits, 3)

    def test_the_position_is_the_one_on_screen(self):
        # Kodi sorts the listing itself, so what the query returned says
        # nothing about where the film ended up.
        container = Container(films=('c', 'a', 'b'))
        Jump(container).toFilm(URL, 'a')
        self.assertEqual(container.selected, [(VIEW, 1)])

    def test_a_film_that_is_not_in_the_listing_selects_nothing(self):
        # A filter can hide it; the cursor then stays where Kodi put it.
        # It looks until the time is up, because a film that is not there
        # yet looks the same as one that is not there at all.
        self.addCleanup(setattr, jump, 'WAIT_SECONDS', jump.WAIT_SECONDS)
        jump.WAIT_SECONDS = 0.3
        container = Container()
        self.assertFalse(Jump(container).toFilm(URL, 'nowhere'))
        self.assertEqual(container.selected, [])

    def test_a_listing_that_was_asked_for_in_vain_is_asked_for_again(self):
        # Kodi sets the path of a listing before it has the items, so a
        # listing asked for while another is still being fetched is lost
        # when that one arrives. Asking again is what saves the jump.
        container = Container(swallows=(0,))
        self.assertTrue(Jump(container).toFilm(URL, 'b'))
        self.assertEqual(container.activated, [URL, URL])
        self.assertEqual(container.selected, [(VIEW, 1)])

    def test_it_waits_for_the_items_rather_than_for_the_path(self):
        # The path is the new listing's while the items are still the old
        # one's, and a film that is not there yet is not a film that is not
        # in the listing.
        container = Container(fills=5)
        self.assertTrue(Jump(container).toFilm(URL, 'c'))
        self.assertEqual(container.selected, [(VIEW, 2)])

    def test_a_listing_that_never_comes(self):
        self.addCleanup(setattr, jump, 'WAIT_SECONDS', jump.WAIT_SECONDS)
        jump.WAIT_SECONDS = 0.2
        container = Container(appears=10 ** 6)
        self.assertFalse(Jump(container).toFilm(URL, 'a'))
        self.assertEqual(container.selected, [])

    def test_kodi_shutting_down_stops_it(self):
        container = Container(abort=True)
        self.assertFalse(Jump(container).toFilm(URL, 'a'))
        self.assertEqual(container.selected, [])


if __name__ == '__main__':
    unittest.main()
