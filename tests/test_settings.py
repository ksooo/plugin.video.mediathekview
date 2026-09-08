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

    def test_the_fallbacks_repeat_the_declared_defaults(self):
        # settingsKodi._getInt carries its own copy of every default so that
        # an unreadable setting cannot end the add-on. Two copies of the same
        # number drift apart unless something holds them together.
        fallbacks = dict((name, int(value)) for (name, value) in
                         re.findall(r"self\._getInt\('([^']+)',\s*(-?\d+)\)", _source()))
        self.assertTrue(fallbacks, 'no fallbacks found - the pattern is wrong')
        declared = dict((setting.get('id'), (setting.find('default').text or '').strip())
                        for setting in _settings())
        for (name, fallback) in sorted(fallbacks.items()):
            self.assertIn(name, declared, '%s is read but not declared' % name)
            self.assertEqual(
                fallback, int(float(declared[name])),
                '%s falls back to %d but settings.xml declares %s'
                % (name, fallback, declared[name]))

    def test_the_declared_ids_are_unique(self):
        ids = [setting.get('id') for setting in _settings()]
        self.assertEqual(sorted(ids), sorted(set(ids)))


class ChangelogTest(unittest.TestCase):
    """What Kodi shows as the changelog.

    <news> is what the add-on browser displays. The addon.xml schema allows
    exactly one of them - a second, language tagged one fails validation with
    "/extension/news[2]" - so there is one, in English. changelog.txt is what
    Kodi falls back to when <news> is empty and holds the same text.
    """

    def _addon(self):
        return ElementTree.parse(os.path.join(support.ADDON_PATH, 'addon.xml')).getroot()

    def _news(self):
        entries = list(self._addon().iter('news'))
        self.assertEqual(len(entries), 1, 'addon.xml allows exactly one <news>')
        return entries[0].text or ''

    def test_the_news_covers_the_declared_version(self):
        version = self._addon().get('version')
        self.assertIn('v' + version, self._news(),
                      'the news does not mention v%s' % version)

    def test_the_changelog_file_repeats_the_news(self):
        with open(os.path.join(support.ADDON_PATH, 'changelog.txt'),
                  encoding='utf-8') as handle:
            self.assertEqual(handle.read().strip(), self._news().strip())


def _source():
    with open(os.path.join(support.ADDON_PATH, 'resources', 'lib',
                           'settingsKodi.py'), encoding='utf-8') as handle:
        return handle.read()


if __name__ == '__main__':
    unittest.main()
