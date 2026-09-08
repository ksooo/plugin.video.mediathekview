# -*- coding: utf-8 -*-
"""
Tests for the search history

SPDX-License-Identifier: MIT
"""

import shutil
import tempfile
import unittest

from tests import support

support.init_app_context()

from resources.lib.searches import RecentSearches, MAX_RECENT_SEARCHES


class Plugin(support.Plugin):

    def __init__(self):
        super(Plugin, self).__init__()
        self.addon_handle = 1


class RecentSearchesTest(unittest.TestCase):
    """The history used to grow for as long as the addon was used.

    add() only ever appended, so nothing bounded it and nothing dropped out.
    """

    def setUp(self):
        self.datapath = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.datapath)
        support.init_app_context(
            settings=support.Settings(datapath=self.datapath, caching=False))
        self.plugin = Plugin()

    def _terms(self, searches):
        recent = RecentSearches(self.plugin)
        for term in searches:
            recent.add(term)
        return [entry['search'] for entry in recent.recents]

    def test_remembers_what_was_searched(self):
        self.assertEqual(self._terms(['Tatort', 'Doku']), ['Tatort', 'Doku'])

    def test_searching_the_same_term_again_does_not_add_it_twice(self):
        self.assertEqual(self._terms(['Tatort', 'tatort']), ['Tatort'])

    def test_stops_growing_at_the_limit(self):
        terms = ['Suche %d' % i for i in range(MAX_RECENT_SEARCHES + 10)]
        self.assertEqual(len(self._terms(terms)), MAX_RECENT_SEARCHES)

    def test_the_oldest_terms_are_the_ones_dropped(self):
        terms = ['Suche %d' % i for i in range(MAX_RECENT_SEARCHES + 1)]
        remembered = self._terms(terms)
        self.assertNotIn('Suche 0', remembered)
        self.assertIn('Suche %d' % MAX_RECENT_SEARCHES, remembered)

    def test_a_survivor_is_kept_across_the_limit(self):
        # Searching an old term again makes it recent, so it has to outlive
        # the ones that were searched before it.
        recent = RecentSearches(self.plugin)
        recent.add('Tatort')
        for i in range(MAX_RECENT_SEARCHES):
            recent.add('Suche %d' % i)
        recent.add('Tatort')
        self.assertIn('Tatort', [entry['search'] for entry in recent.recents])

    def test_the_limit_survives_saving_and_loading(self):
        recent = RecentSearches(self.plugin)
        for i in range(MAX_RECENT_SEARCHES + 5):
            recent.add('Suche %d' % i)
        recent.save()
        self.assertEqual(len(RecentSearches(self.plugin).load().recents),
                         MAX_RECENT_SEARCHES)


if __name__ == '__main__':
    unittest.main()
