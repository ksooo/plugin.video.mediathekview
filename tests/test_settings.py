# -*- coding: utf-8 -*-
"""
Holds settings.xml against the rules Kodi applies when reading it

SPDX-License-Identifier: MIT
"""

import os
import re
import unittest
from xml.etree import ElementTree

from tests import support

_SETTINGS = os.path.join(support.ADDON_PATH, 'resources', 'settings.xml')

# SettingLevel::Internal. Kodi hides these and, uniquely, lets them do without
# a <control>.
_INTERNAL = 4


def _settings():
    for setting in ElementTree.parse(_SETTINGS).getroot().iter('setting'):
        yield setting


def _level(setting):
    element = setting.find('level')
    return int(element.text) if element is not None else 1


class SettingsTest(unittest.TestCase):

    def test_every_setting_has_a_control_or_is_internal(self):
        # Kodi drops a setting that has neither, with "missing <control> tag"
        # in the log. getSetting then hands out an empty string, and the int()
        # calls in settingsKodi turn that into a ValueError that takes down
        # both the plugin and the service on start. That is what 1.0.0 did.
        for setting in _settings():
            if setting.find('control') is None:
                self.assertEqual(
                    _level(setting), _INTERNAL,
                    '%s has no <control>, so it has to be level %d'
                    % (setting.get('id'), _INTERNAL))

    def test_every_setting_has_a_default(self):
        # Without one the first read comes back empty, which the int() calls
        # in settingsKodi cannot survive either.
        for setting in _settings():
            self.assertIsNotNone(setting.find('default'),
                                 '%s has no <default>' % setting.get('id'))

    def test_settings_read_as_numbers_default_to_one(self):
        numeric = set(re.findall(r"int\(float\(self\._addonClass\.getSetting\('([^']+)'\)\)\)",
                                 _source())
                      ) | set(re.findall(r"int\(self\._addonClass\.getSetting\('([^']+)'\)\)",
                                         _source()))
        self.assertTrue(numeric, 'no numeric settings found - the pattern is wrong')
        for setting in _settings():
            if setting.get('id') in numeric:
                default = setting.find('default')
                self.assertTrue(
                    (default.text or '').strip().lstrip('-').isdigit(),
                    '%s is read as a number but defaults to %r'
                    % (setting.get('id'), default.text))

    def test_the_declared_ids_are_unique(self):
        ids = [setting.get('id') for setting in _settings()]
        self.assertEqual(sorted(ids), sorted(set(ids)))


def _source():
    with open(os.path.join(support.ADDON_PATH, 'resources', 'lib',
                           'settingsKodi.py'), encoding='utf-8') as handle:
        return handle.read()


if __name__ == '__main__':
    unittest.main()
