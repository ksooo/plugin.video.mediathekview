# -*- coding: utf-8 -*-
"""
Tests for hiding the audio described version where the film itself is listed

SPDX-License-Identifier: MIT
"""

import unittest

from tests import support

support.init_app_context()

from resources.lib.variants import (SIGN_LANGUAGE, plainTitle,
                                    withoutAudioDescription, withoutSignLanguage)


def _film(title, show='Doppelhaushälfte', channel='ZDFneo'):
    return ('hash', title, show, channel)


def _titles(rows):
    return [row[1] for row in rows]


class PlainTitleTest(unittest.TestCase):
    """Which titles are an audio described version of another."""

    def test_the_marker_in_brackets(self):
        self.assertEqual(plainTitle('Chancengleichheit (Audiodeskription)'),
                         'Chancengleichheit')

    def test_the_marker_without_brackets(self):
        self.assertEqual(plainTitle('Tatort: Der Fall Audiodeskription'),
                         'Tatort: Der Fall')

    def test_the_marker_hung_on_with_a_separator(self):
        # "Der Fall (1/2) - Audiodeskription" beside "Der Fall (1/2)".
        self.assertEqual(plainTitle('Der Fall (1/2) - Audiodeskription'),
                         'Der Fall (1/2)')

    def test_the_older_name_for_it(self):
        self.assertEqual(plainTitle('Der Bergdoktor (Hörfassung)'),
                         'Der Bergdoktor')
        self.assertEqual(plainTitle('Der Bergdoktor (mit Audiodeskription)'),
                         'Der Bergdoktor')

    def test_the_short_form_needs_its_brackets(self):
        # A title could end in those two letters by accident.
        self.assertEqual(plainTitle('Die Sendung (AD)'), 'Die Sendung')
        self.assertIsNone(plainTitle('Reise nach Bad Gastein AD'))

    def test_a_marker_that_is_not_at_the_end_is_not_one(self):
        # The film list has 43 of these, all of them "| Audiodeskription |"
        # in the middle of a title, and none of them has a twin.
        self.assertIsNone(plainTitle('Behindert feiern | Audiodeskription | 100percentme'))

    def test_an_ordinary_title(self):
        self.assertIsNone(plainTitle('Chancengleichheit'))
        self.assertIsNone(plainTitle(''))
        self.assertIsNone(plainTitle(None))


class SignLanguageTest(unittest.TestCase):
    """The other version the broadcasters mark, in the same three forms."""

    def _plain(self, title):
        return plainTitle(title, SIGN_LANGUAGE)

    def test_the_forms_it_is_written_in(self):
        for title in ('Westpol (Gebärdensprache)',
                      'Tagesschau 18:00 Uhr - mit Gebärdensprache',
                      'Die Sendung in Gebärdensprache',
                      'Die Sendung (DGS)'):
            self.assertIsNotNone(self._plain(title), title)

    def test_the_short_form_needs_its_brackets(self):
        self.assertIsNone(self._plain('Der Kanal DGS'))

    def test_it_is_not_the_audio_described_marker(self):
        self.assertIsNone(self._plain('Westpol (Audiodeskription)'))
        self.assertIsNone(plainTitle('Westpol (Gebärdensprache)'))

    def test_the_version_beside_the_film_is_dropped(self):
        rows = [_film('Westpol'), _film('Westpol (Gebärdensprache)')]
        self.assertEqual(_titles(withoutSignLanguage(rows)), ['Westpol'])

    def test_the_only_version_there_is_stays(self):
        # 2399 of the marked films have no twin.
        rows = [_film('Westpol (Gebärdensprache)')]
        self.assertEqual(len(withoutSignLanguage(rows)), 1)

    def test_the_two_filters_do_not_touch_each_others_films(self):
        rows = [_film('Westpol'), _film('Westpol (Gebärdensprache)'),
                _film('Westpol (Audiodeskription)')]
        self.assertEqual(_titles(withoutSignLanguage(rows)),
                         ['Westpol', 'Westpol (Audiodeskription)'])
        self.assertEqual(_titles(withoutAudioDescription(rows)),
                         ['Westpol', 'Westpol (Gebärdensprache)'])


class WithoutAudioDescriptionTest(unittest.TestCase):

    def test_the_version_beside_the_film_is_dropped(self):
        rows = [_film('Chancengleichheit'),
                _film('Chancengleichheit (Audiodeskription)')]
        self.assertEqual(_titles(withoutAudioDescription(rows)),
                         ['Chancengleichheit'])

    def test_the_only_version_there_is_stays(self):
        # 2153 of the marked films have no twin, and somebody wants those.
        rows = [_film('Gut für die Nachbarschaft (Audiodeskription)')]
        self.assertEqual(_titles(withoutAudioDescription(rows)),
                         ['Gut für die Nachbarschaft (Audiodeskription)'])

    def test_the_twin_has_to_be_of_the_same_show(self):
        rows = [_film('Chancengleichheit', show='Doppelhaushälfte'),
                _film('Chancengleichheit (Audiodeskription)', show='Dunkelstadt')]
        self.assertEqual(len(withoutAudioDescription(rows)), 2)

    def test_the_twin_has_to_be_of_the_same_channel(self):
        # The same show runs on more than one channel, and a listing can hold
        # both, where each channel's own version belongs to it.
        rows = [_film('Chancengleichheit', channel='ZDF'),
                _film('Chancengleichheit (Audiodeskription)', channel='ZDFneo')]
        self.assertEqual(len(withoutAudioDescription(rows)), 2)

    def test_the_order_of_the_others_is_untouched(self):
        rows = [_film('Brian'), _film('Brian (Audiodeskription)'),
                _film('Vorrundenaus'), _film('Schall und Rauch')]
        self.assertEqual(_titles(withoutAudioDescription(rows)),
                         ['Brian', 'Vorrundenaus', 'Schall und Rauch'])

    def test_nothing_to_do(self):
        self.assertEqual(withoutAudioDescription([]), [])
        rows = [_film('Brian'), _film('Vorrundenaus')]
        self.assertEqual(len(withoutAudioDescription(rows)), 2)


if __name__ == '__main__':
    unittest.main()
