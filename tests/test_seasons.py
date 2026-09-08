# -*- coding: utf-8 -*-
"""
Tests for the season and episode numbers hidden in the titles

SPDX-License-Identifier: MIT
"""

import unittest

from tests import support

support.init_app_context()

import resources.lib.seasons as seasons
from resources.lib.seasons import group, ofSeason, seasonOf, splitEpisode


def _row(title, channel='ARD'):
    """A row of the film query: only the title and the channel matter here."""
    return ('hash', title, 'Sendung', channel, '', 60, 0, '', 'u', '', '')


class SplitEpisodeTest(unittest.TestCase):
    """Season and episode live inside the title MediathekView writes.

    Of 715993 films, 57150 carry the marker in one of these two shapes. The
    other forms it uses - "Folge 6", "(1/4)", "Teil 2" - are fewer and
    ambiguous, "(1/4)" as often meaning part one of four, so they stay put.
    """

    def test_the_usual_shape(self):
        self.assertEqual(splitEpisode('Nordspanien von oben (S01/E11)'),
                         ('Nordspanien von oben', 1, 11))

    def test_the_shape_without_a_slash(self):
        self.assertEqual(splitEpisode('Kulturzeit vom 30.04.2024 (S2024E80)'),
                         ('Kulturzeit vom 30.04.2024', 2024, 80))

    def test_a_year_is_a_season_like_any_other(self):
        self.assertEqual(splitEpisode('37: Wir wollten nur raus (S2022/E12)')[1], 2022)

    def test_what_follows_the_marker_stays(self):
        self.assertEqual(splitEpisode('Du bist mehr! (S2024/E52) (Gebärdensprache)'),
                         ('Du bist mehr! (Gebärdensprache)', 2024, 52))

    def test_a_title_without_a_marker_is_handed_back_as_it_came(self):
        self.assertEqual(splitEpisode('Tagesschau'), ('Tagesschau', None, None))

    def test_the_ambiguous_forms_are_left_alone(self):
        for title in ('Abenteuer Linienbus (1/4)', 'Davos 1917 (Folge 3)',
                      'Die wilden Philippinen - Teil 1', 'Vier Saiten (9)'):
            self.assertEqual(splitEpisode(title), (title, None, None))

    def test_the_season_of_a_row(self):
        self.assertEqual(seasonOf(_row('Erben (S05/E02)')), 5)
        self.assertIsNone(seasonOf(_row('Tagesschau')))


class GroupTest(unittest.TestCase):
    """Whether a show's films go behind seasons or stay in one list.

    Of 11209 shows only 604 have more than one season, and a good hundred of
    those are daily formats where the numbering is the exception - "heute
    19:00 Uhr" has 4851 films, 2604 of them unnumbered. Those are better left
    flat than sorted into seasons that hold half of them.
    """

    def _rows(self, *titles):
        return [_row(title) for title in titles]

    def test_a_series_is_sorted_into_its_seasons(self):
        rows = self._rows('Erben (S05/E02)', 'Ufo (S06/E07)', 'Musical (S05/E03)')
        (grouped, loose) = group(rows)
        self.assertEqual([number for (number, _) in grouped], [5, 6])
        self.assertEqual(len(grouped[0][1]), 2)
        self.assertEqual(loose, [])

    def test_a_show_with_one_season_stays_flat(self):
        # The extra level would be a click that leads to everything.
        rows = self._rows('Erben (S05/E02)', 'Ufo (S05/E07)')
        self.assertEqual(group(rows), ([], rows))

    def test_a_show_without_numbers_stays_flat(self):
        rows = self._rows('Tagesschau', 'Tagesthemen')
        self.assertEqual(group(rows), ([], rows))

    def test_a_show_that_numbers_only_some_of_its_films_stays_flat(self):
        rows = self._rows('Erben (S05/E02)', 'Ufo (S06/E07)',
                          'Sondersendung', 'Extra', 'Nachschlag')
        self.assertEqual(group(rows), ([], rows))

    def test_the_few_unnumbered_films_of_a_series_stay_loose(self):
        rows = self._rows(*(['Folge (S0%d/E01)' % (n % 3 + 1) for n in range(9)]
                            + ['Making of']))
        (grouped, loose) = group(rows)
        self.assertEqual(len(grouped), 3)
        self.assertEqual([row[1] for row in loose], ['Making of'])

    def test_where_the_line_is_drawn(self):
        self.assertEqual(seasons.MINIMUM_SEASONS, 2)
        self.assertEqual(seasons.MINIMUM_MARKED_SHARE, 0.8)


class OfSeasonTest(unittest.TestCase):

    def test_picks_the_films_of_one_season(self):
        rows = [_row('Erben (S05/E02)'), _row('Ufo (S06/E07)'), _row('Musical (S05/E03)')]
        self.assertEqual([row[1] for row in ofSeason(rows, 5)],
                         ['Erben (S05/E02)', 'Musical (S05/E03)'])

    def test_a_season_nobody_named(self):
        self.assertEqual(ofSeason([_row('Tagesschau')], 1), [])


if __name__ == '__main__':
    unittest.main()
