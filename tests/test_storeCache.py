# -*- coding: utf-8 -*-
"""
Tests for the query result cache

SPDX-License-Identifier: MIT
"""

import os
import shutil
import tempfile
import unittest

from tests import support

support.init_app_context()

from resources.lib.storeCache import StoreCache


class StoreCacheTest(unittest.TestCase):

    def setUp(self):
        self.datapath = tempfile.mkdtemp()
        self.settings = support.Settings(datapath=self.datapath, lastUpdate=100)
        support.init_app_context(settings=self.settings)
        self.cache = StoreCache()

    def tearDown(self):
        shutil.rmtree(self.datapath)

    def test_stores_and_returns_a_result(self):
        self.cache.save_cache('films', 'channel=ARD', [['a'], ['b']])
        self.assertEqual(self.cache.load_cache('films', 'channel=ARD'),
                         [['a'], ['b']])

    def test_two_conditions_of_one_type_do_not_evict_each_other(self):
        # Every file used to be named after the request type alone, so the
        # second save overwrote the first and going back to the first
        # condition always missed.
        self.cache.save_cache('films', 'channel=ARD', [['ard']])
        self.cache.save_cache('films', 'channel=ZDF', [['zdf']])
        self.assertEqual(self.cache.load_cache('films', 'channel=ARD'), [['ard']])
        self.assertEqual(self.cache.load_cache('films', 'channel=ZDF'), [['zdf']])

    def test_an_unknown_condition_is_a_miss(self):
        self.cache.save_cache('films', 'channel=ARD', [['ard']])
        self.assertIsNone(self.cache.load_cache('films', 'channel=BR'))

    def test_a_database_update_makes_the_entry_stale(self):
        self.cache.save_cache('films', 'channel=ARD', [['ard']])
        self.settings.setLastUpdate(200)
        self.assertIsNone(self.cache.load_cache('films', 'channel=ARD'))

    def test_purge_drops_every_entry(self):
        self.cache.save_cache('films', 'channel=ARD', [['ard']])
        self.cache.save_cache('channels', '', [['ARD']])
        self.cache.purge()
        self.assertIsNone(self.cache.load_cache('films', 'channel=ARD'))
        self.assertIsNone(self.cache.load_cache('channels', ''))

    def test_purge_also_removes_files_from_the_old_layout(self):
        legacy = os.path.join(self.datapath, 'films.cache')
        with open(legacy, 'w', encoding='utf-8') as handle:
            handle.write('{}')
        self.cache.purge()
        self.assertFalse(os.path.exists(legacy))

    def test_purge_survives_a_missing_directory(self):
        self.cache.purge()

    def test_caching_switched_off_stores_nothing(self):
        support.init_app_context(
            settings=support.Settings(datapath=self.datapath, caching=False))
        cache = StoreCache()
        cache.save_cache('films', 'channel=ARD', [['ard']])
        self.assertIsNone(cache.load_cache('films', 'channel=ARD'))


if __name__ == '__main__':
    unittest.main()
