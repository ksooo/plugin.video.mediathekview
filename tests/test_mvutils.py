# -*- coding: utf-8 -*-
"""
Tests for the string helpers in mvutils

SPDX-License-Identifier: MIT
"""

import unittest

from tests import support  # noqa: F401  (sets up sys.path)

from resources.lib import mvutils


class CoalesceTest(unittest.TestCase):

    def test_returns_first_value_that_is_not_none(self):
        self.assertEqual(mvutils.coalesce(None, None, 'x', 'y'), 'x')

    def test_zero_is_a_value(self):
        self.assertEqual(mvutils.coalesce(None, 0, 1), 0)

    def test_returns_none_when_everything_is_none(self):
        self.assertIsNone(mvutils.coalesce(None, None))


class MakeSearchStringTest(unittest.TestCase):

    def test_uppercases_and_drops_punctuation(self):
        self.assertEqual(mvutils.make_search_string('Die Sendung mit der Maus!'),
                         'DIE SENDUNG MIT DER MAUS')

    def test_drops_umlauts(self):
        # The search column is filled with this, so a title spelled with an
        # umlaut is only findable when the search term loses it as well.
        self.assertEqual(mvutils.make_search_string('Tatort München'), 'TATORT MNCHEN')

    def test_keeps_digits_and_the_allowed_punctuation(self):
        self.assertEqual(mvutils.make_search_string('Terra X #1_2-3'), 'TERRA X #1_2-3')


class MakeDurationTest(unittest.TestCase):

    def test_converts_hours_minutes_seconds(self):
        self.assertEqual(mvutils.make_duration('01:02:03'), 3723)

    def test_zero_duration(self):
        self.assertEqual(mvutils.make_duration('00:00:00'), 0)

    def test_none_is_zero(self):
        self.assertEqual(mvutils.make_duration(None), 0)

    def test_malformed_input_is_zero(self):
        self.assertEqual(mvutils.make_duration('12:34'), 0)


class CleanupFilenameTest(unittest.TestCase):

    def test_keeps_umlauts(self):
        self.assertEqual(mvutils.cleanup_filename('Tatort München'), 'Tatort München')

    def test_drops_path_separators(self):
        self.assertEqual(mvutils.cleanup_filename('a/b\\c:d'), 'abcd')

    def test_strips_surrounding_whitespace(self):
        self.assertEqual(mvutils.cleanup_filename('  Titel  '), 'Titel')


if __name__ == '__main__':
    unittest.main()
