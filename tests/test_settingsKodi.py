# -*- coding: utf-8 -*-
"""
Tests for reading settings that Kodi could not deliver

SPDX-License-Identifier: MIT
"""

import unittest

from tests import support

support.init_app_context()

import xbmc

from resources.lib.settingsKodi import SettingsKodi


class Addon(support.Addon):
    """An addon whose settings can be made to answer badly."""

    def __init__(self, values):
        super(Addon, self).__init__()
        self.settings = values

    def getSetting(self, key):
        return self.settings.get(key, '')


class GetIntTest(unittest.TestCase):
    """A setting Kodi rejected comes back as an empty string.

    1.0.0 ran int() on that and died before the plugin or the service could
    show anything. Falling back to the declared default keeps the add-on
    usable whatever went wrong with the settings.
    """

    def setUp(self):
        self.logged = []
        xbmc.log = lambda message, level=0: self.logged.append(message)

    def _settings(self, **values):
        settings = SettingsKodi(Addon(values))
        # The constructor logs a line of its own; only what the reads say is
        # of interest here.
        self.logged = []
        return settings

    def test_reads_a_number(self):
        self.assertEqual(self._settings(maxresults='2000').getMaxResults(), 2000)

    def test_reads_a_number_written_as_a_decimal(self):
        self.assertEqual(self._settings(minlength='5.0').getMinLength(), 5)

    def test_an_empty_setting_falls_back(self):
        self.assertEqual(self._settings(maxresults='').getMaxResults(), 1000)

    def test_a_missing_setting_falls_back(self):
        self.assertEqual(self._settings().getUpdateCheckIntervel(), 30)

    def test_a_setting_that_is_not_a_number_falls_back(self):
        self.assertEqual(self._settings(dbport='localhost').getDatabasePort(), 3306)

    def test_the_two_that_took_down_1_0_0(self):
        settings = self._settings()
        self.assertEqual(settings.getDelayStartupSec(), 10)
        self.assertEqual(settings.getLastUpdate(), 0)

    def test_says_which_setting_was_unreadable(self):
        self._settings(maxage='').getMaxAge()
        self.assertTrue(any('maxage' in message for message in self.logged), self.logged)

    def test_a_good_setting_is_not_logged(self):
        self._settings(maxage='7').getMaxAge()
        self.assertEqual(self.logged, [])

    def test_the_multiplied_settings_keep_their_unit(self):
        self.assertEqual(self._settings(maxage='3').getMaxAge(), 3 * 86400)
        self.assertEqual(self._settings(updinterval='4').getDatabaseUpdateInvterval(),
                         4 * 3600)


if __name__ == '__main__':
    unittest.main()
