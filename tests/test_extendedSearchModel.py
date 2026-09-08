# -*- coding: utf-8 -*-
"""
Tests for how a search turns into SQL

SPDX-License-Identifier: MIT
"""

import unittest

from tests import support

support.init_app_context()

from resources.lib.extendedSearchModel import ExtendedSearchModel


def _model(**fields):
    support.init_app_context(settings=support.Settings(maxResults=0, minLength=0))
    model = ExtendedSearchModel('')
    model.reset()
    for (name, value) in fields.items():
        getattr(model, 'set' + name[0].upper() + name[1:])(value)
    return model


class MixedSearchTest(unittest.TestCase):
    """One term, matched against several columns - what the quick search does."""

    def test_matches_the_show_or_the_title(self):
        (sql, params) = _model(mixedSearch='Tatort').generateMixedSearch()
        self.assertEqual(' ( showname like ? or title like ? )', sql)
        self.assertEqual(['%Tatort%', '%Tatort%'], params)

    def test_nothing_without_a_term(self):
        self.assertEqual(('', []), _model().generateMixedSearch())

    def test_several_terms_widen_the_search(self):
        (sql, params) = _model(mixedSearch='Tatort|Polizeiruf').generateMixedSearch()
        self.assertEqual(4, sql.count('like ?'))
        self.assertEqual(0, sql.count(' and '))
        self.assertEqual(['%Tatort%', '%Tatort%', '%Polizeiruf%', '%Polizeiruf%'], params)


class FieldsTest(unittest.TestCase):
    """Separate fields of the extended search.

    They used to be poured into one parenthesis joined by "or", so filling a
    second field widened the result instead of narrowing it. Each field is now
    a condition of its own, and the query joins them with AND.
    """

    def test_the_show_field_matches_loosely(self):
        (sql, params) = _model(show='Tatort').generateShow()
        self.assertEqual(' ( showname like ? )', sql)
        self.assertEqual(['%Tatort%'], params)

    def test_the_show_field_matches_exactly_when_asked(self):
        model = _model(show='LIVESTREAM')
        model.setExactMatchForShow(True)
        (sql, params) = model.generateShow()
        self.assertIn('showname in (', sql)
        self.assertEqual(['LIVESTREAM'], params)

    def test_the_title_field(self):
        (sql, params) = _model(title='München').generateTitle()
        self.assertEqual(' ( title like ? )', sql)
        self.assertEqual(['%München%'], params)

    def test_the_description_field(self):
        (sql, params) = _model(description='Krimi').generateDescription()
        self.assertEqual(' ( description like ? )', sql)
        self.assertEqual(['%Krimi%'], params)

    def test_several_values_in_one_field_widen_it(self):
        (sql, params) = _model(title='München|Hamburg').generateTitle()
        self.assertEqual(' ( title like ? or title like ? )', sql)
        self.assertEqual(['%München%', '%Hamburg%'], params)

    def test_an_empty_field_contributes_nothing(self):
        model = _model(show='Tatort')
        self.assertEqual(('', []), model.generateTitle())
        self.assertEqual(('', []), model.generateDescription())


class CacheKeyTest(unittest.TestCase):

    def test_the_mixed_term_reaches_the_cache_key(self):
        # Without it every quick search would share one cache entry.
        first = _model(mixedSearch='Tatort').getCacheKey()
        second = _model(mixedSearch='Polizeiruf').getCacheKey()
        self.assertNotEqual(first, second)

    def test_a_mixed_term_differs_from_the_same_text_in_a_field(self):
        self.assertNotEqual(_model(mixedSearch='Tatort').getCacheKey(),
                            _model(show='Tatort').getCacheKey())


if __name__ == '__main__':
    unittest.main()
