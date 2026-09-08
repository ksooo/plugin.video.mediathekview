# -*- coding: utf-8 -*-
"""
Tests for the search menu

SPDX-License-Identifier: MIT
"""

import os
import shutil
import tempfile
import unittest

from tests import support

support.init_app_context()


class Plugin(support.Plugin):
    """Records the directory the screen builds."""

    def __init__(self):
        super(Plugin, self).__init__()
        self.items = []

    def add_folder_item(self, name, params, contextmenu=None, icon=None, fanart=None):
        self.items.append((name, params))

    def end_of_directory(self, succeeded=True, update_listing=False, cache_to_disc=False):
        pass


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

    def test_a_fresh_install_offers_only_a_new_search(self):
        self.assertEqual(self._menu(), [30931])

    def test_the_history_appears_once_something_was_searched(self):
        self._write('recent_std_searches.json',
                    '[{"search": "Tatort", "when": 1}]')
        self.assertEqual(self._menu(), [30931, 30907])

    def test_an_empty_file_counts_as_nothing(self):
        self._write('recent_std_searches.json', '[]')
        self.assertEqual(self._menu(), [30931])


if __name__ == '__main__':
    unittest.main()
