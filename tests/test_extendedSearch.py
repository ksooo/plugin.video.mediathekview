# -*- coding: utf-8 -*-
"""
Tests for the saved searches screen

SPDX-License-Identifier: MIT
"""

import os
import shutil
import tempfile
import unittest

from tests import support

support.init_app_context()

from resources.lib.extendedSearch import ExtendedSearch


class Plugin(support.Plugin):
    """Records the directory the screen builds."""

    def __init__(self):
        super(Plugin, self).__init__()
        self.items = []

    def add_folder_item(self, name, params, contextmenu=None, icon=None, fanart=None):
        self.items.append((name, params))

    def end_of_directory(self, succeeded=True, update_listing=False, cache_to_disc=False):
        pass


class ShowListTest(unittest.TestCase):
    """What the list of saved searches holds.

    It used to open with a "New search ..." item sitting above the saved ones.
    A special item among real entries collides with a saved search of the same
    name and makes the level inconsistent, so creating one is a way in of its
    own, in the search menu.
    """

    def setUp(self):
        self.datapath = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.datapath)
        support.init_app_context(
            settings=support.Settings(datapath=self.datapath, caching=False))
        self.plugin = Plugin()

    def _showList(self, saved):
        with open(os.path.join(self.datapath, 'searchConfig.json'),
                  'w', encoding='utf-8') as handle:
            handle.write(saved)
        search = ExtendedSearch(self.plugin, None, None, None)
        search.showList()
        return self.plugin.items

    def test_an_empty_list_stays_empty(self):
        self.assertEqual(self._showList('[]'), [])

    def test_lists_only_the_saved_searches_most_recent_first(self):
        items = self._showList(
            '[{"id": 1, "name": "Tatort", "when": 1}, '
            ' {"id": 2, "name": "Doku", "when": 2}]')
        self.assertEqual([name for (name, _) in items], ['Doku', 'Tatort'])

    def test_every_entry_runs_a_saved_search(self):
        items = self._showList('[{"id": 7, "name": "Tatort", "when": 1}]')
        (_, params) = items[0]
        self.assertEqual(params['extendedSearchAction'], 'RUN')
        self.assertEqual(params['searchId'], 7)

    def test_nothing_offers_to_create_one(self):
        items = self._showList('[{"id": 1, "name": "Tatort", "when": 1}]')
        actions = [params.get('extendedSearchAction') for (_, params) in items]
        self.assertNotIn('NEW', actions)


class SearchMenuTest(unittest.TestCase):
    """Which ways in the search menu offers.

    A list that would be empty is left out. Opening one gives a window with
    nothing in it, and Kodi only puts a ".." in front of a list when the user
    turned parent folder items on, so it can turn into a dead end.
    """

    def setUp(self):
        self.datapath = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.datapath)
        support.init_app_context(
            settings=support.Settings(datapath=self.datapath, caching=False))

    def _write(self, name, content):
        with open(os.path.join(self.datapath, name), 'w', encoding='utf-8') as handle:
            handle.write(content)

    def _menu(self):
        from resources.lib.plugin import MediathekViewPlugin
        plugin = Plugin()
        MediathekViewPlugin.show_search_menu(plugin)
        return [name for (name, _) in plugin.items]

    def test_a_fresh_install_offers_only_the_two_ways_to_start(self):
        self.assertEqual(self._menu(), [30931, 30911])

    def test_the_history_appears_once_something_was_searched(self):
        self._write('recent_std_searches.json',
                    '[{"search": "Tatort", "when": 1}]')
        self.assertEqual(self._menu(), [30931, 30911, 30907])

    def test_the_saved_searches_appear_once_one_was_saved(self):
        self._write('searchConfig.json', '[{"id": 1, "name": "Tatort", "when": 1}]')
        self.assertEqual(self._menu(), [30931, 30911, 30910])

    def test_both_appear_when_both_are_filled(self):
        self._write('recent_std_searches.json', '[{"search": "Tatort", "when": 1}]')
        self._write('searchConfig.json', '[{"id": 1, "name": "Doku", "when": 1}]')
        self.assertEqual(self._menu(), [30931, 30911, 30907, 30910])

    def test_an_empty_file_counts_as_nothing(self):
        self._write('recent_std_searches.json', '[]')
        self._write('searchConfig.json', '[]')
        self.assertEqual(self._menu(), [30931, 30911])


if __name__ == '__main__':
    unittest.main()
