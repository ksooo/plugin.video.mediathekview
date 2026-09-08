# -*- coding: utf-8 -*-
"""
Holds the string ids used in the code against the language files

SPDX-License-Identifier: MIT
"""

import os
import re
import unittest
from xml.etree import ElementTree

from tests import support

_LANGUAGE_DIR = os.path.join(support.ADDON_PATH, 'resources', 'language')
_SOURCE_DIRS = ('resources/lib',)
_ROOT_SOURCES = ('addon.py', 'service.py', 'contextMenu.py')

# Addon string ids live in this range; anything else in the sources that looks
# like a number is not a string id.
_FIRST_ID = 30000
_LAST_ID = 30999


def _language_files():
    for name in sorted(os.listdir(_LANGUAGE_DIR)):
        path = os.path.join(_LANGUAGE_DIR, name, 'strings.po')
        if os.path.isfile(path):
            yield (name, path)


def _defined_ids(path):
    with open(path, encoding='utf-8') as handle:
        return set(int(i) for i in re.findall(r'msgctxt "#(\d+)"', handle.read()))


def _source_files():
    for name in _ROOT_SOURCES:
        yield os.path.join(support.ADDON_PATH, name)
    for directory in _SOURCE_DIRS:
        for (root, _, names) in os.walk(os.path.join(support.ADDON_PATH, directory)):
            for name in sorted(names):
                if name.endswith('.py'):
                    yield os.path.join(root, name)


def _referenced_ids():
    """Every string id the sources mention, with where it was found.

    Matching the bare literal rather than the call around it: the ids are
    passed on in too many shapes to enumerate - directly, through a
    conditional, as a dict value - and every number in this range in the
    sources is in fact a string id.
    """
    literal = re.compile(r'(?<![\w.])(3\d{4})(?![\w.])')
    found = {}
    for path in _source_files():
        with open(path, encoding='utf-8') as handle:
            for (number, line) in enumerate(handle, 1):
                for match in literal.finditer(line):
                    string_id = int(match.group(1))
                    if _FIRST_ID <= string_id <= _LAST_ID:
                        found.setdefault(string_id, []).append(
                            '%s:%d' % (os.path.relpath(path, support.ADDON_PATH), number))
    return found


def _xml_ids():
    """String ids the XML files point at: labels, helps and control headings."""
    found = {}
    for name in ('addon.xml', os.path.join('resources', 'settings.xml')):
        path = os.path.join(support.ADDON_PATH, name)
        tree = ElementTree.parse(path)
        for element in tree.getroot().iter():
            values = [element.get('label'), element.get('help')]
            if element.tag in ('label', 'heading'):
                values.append((element.text or '').strip())
            for value in values:
                if value and value.isdigit():
                    string_id = int(value)
                    if _FIRST_ID <= string_id <= _LAST_ID:
                        found.setdefault(string_id, []).append(name)
    return found


class StringsTest(unittest.TestCase):

    def test_every_id_used_in_the_xml_files_exists_in_every_language(self):
        # The EPG context menu takes its label from addon.xml, and every
        # setting takes its label and help from settings.xml. Kodi shows a
        # blank entry for an id no language file defines.
        referenced = _xml_ids()
        self.assertTrue(referenced, 'no string ids found in the xml files')
        for (language, path) in _language_files():
            missing = sorted(set(referenced) - _defined_ids(path))
            self.assertEqual(
                missing, [],
                '%s lacks %s, used in %s' % (
                    language, missing,
                    '; '.join(place for i in missing for place in referenced[i])))

    def test_every_referenced_id_exists_in_every_language(self):
        # play_movie_with_subs used to ask for 30991, which exists in no
        # language file, so Kodi showed an empty message under a heading that
        # was itself the wrong string.
        referenced = _referenced_ids()
        self.assertTrue(referenced, 'no string ids found - the pattern is wrong')
        for (language, path) in _language_files():
            defined = _defined_ids(path)
            missing = sorted(set(referenced) - defined)
            self.assertEqual(
                missing, [],
                '%s lacks %s, used at %s' % (
                    language, missing,
                    '; '.join(place for i in missing for place in referenced[i])))

    def test_the_languages_define_the_same_ids(self):
        by_language = dict((language, _defined_ids(path))
                           for (language, path) in _language_files())
        self.assertGreaterEqual(len(by_language), 2)
        reference = sorted(by_language.values(), key=len, reverse=True)[0]
        for (language, defined) in by_language.items():
            self.assertEqual(sorted(reference - defined), [],
                             '%s is missing ids the others define' % language)


if __name__ == '__main__':
    unittest.main()
