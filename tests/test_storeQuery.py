# -*- coding: utf-8 -*-
"""
Tests for the shared query layer

SPDX-License-Identifier: MIT
"""

import unittest

from tests import support

support.init_app_context()

from resources.lib.storeQuery import StoreQuery


class Store(StoreQuery):
    """StoreQuery against a recording connection instead of a database."""

    def __init__(self, connection):
        super(Store, self).__init__()
        self._connection = connection

    def getConnection(self):
        return self._connection


def _store(results=None, error=None):
    connection = support.Connection(results=results, error=error)
    return (Store(connection), connection)


class GetStatusTest(unittest.TestCase):

    def setUp(self):
        support.init_app_context(settings=support.Settings(caching=False))

    def test_reads_the_status_and_the_counts(self):
        (store, _) = _store(results=[
            [('IDLE', 100, 90, 80, 3)],
            [(29, 5000, 400000)],
        ])
        status = store.get_status()
        self.assertEqual(status['status'], 'IDLE')
        self.assertEqual(status['lastUpdate'], 100)
        self.assertEqual(status['mov'], 400000)

    def test_a_failure_is_not_reported_as_an_empty_database(self):
        # It used to swallow the exception and hand back the initial dict,
        # whose mov is 0. The updater reads that as "the database I just
        # downloaded is empty", throws it away and downloads it again.
        (store, _) = _store(error=RuntimeError('database is locked'))
        with self.assertRaises(RuntimeError):
            store.get_status()

    def test_a_failure_is_logged(self):
        (store, _) = _store(error=RuntimeError('database is locked'))
        try:
            store.get_status()
        except RuntimeError:
            pass
        import resources.lib.appContext as app_context
        logged = [text for (level, text) in app_context.MVLOGGER.messages
                  if level == 'error']
        self.assertTrue(any('database is locked' in text for text in logged),
                        'the reason has to reach the log')


class FilmOrderTest(unittest.TestCase):
    """What order the films come back in.

    MediathekView publishes a whole season at one timestamp, so the broadcast
    date alone leaves sixteen films in whatever order the database happens to
    find them - and that order changes with every update.
    """

    def setUp(self):
        support.init_app_context(settings=support.Settings(caching=False))

    def test_the_order_is_settled_beyond_the_date(self):
        import resources.lib.extendedSearchModel as extendedSearchModel
        (store, connection) = _store(results=[[]])
        store.extendedSearchQuery(extendedSearchModel.ExtendedSearchModel(''))
        statement = connection.statements[0]
        self.assertIn('ORDER BY aired DESC, showname ASC, title ASC', statement)


class RetrieveFilmInfoTest(unittest.TestCase):

    def setUp(self):
        support.init_app_context(settings=support.Settings(caching=False))

    def test_passes_the_film_id_as_a_parameter(self):
        # The id arrives from the plugin url, so it must not be pasted into
        # the statement.
        (store, connection) = _store(results=[
            [('d41d8cd9', 'Titel', 'Sendung', 'ARD', '', 60, 0, '', 'u', '', '')],
        ])
        store.retrieve_film_info('d41d8cd9')
        (statement, params) = connection.executed[0]
        self.assertNotIn('d41d8cd9', statement)
        self.assertEqual(params, ('d41d8cd9',))

    def test_an_id_holding_a_quote_does_not_reach_the_statement(self):
        (store, connection) = _store(results=[[]])
        store.retrieve_film_info("' OR '1'='1")
        (statement, params) = connection.executed[0]
        self.assertEqual(statement.count('?'), 1)
        self.assertNotIn('OR', statement)
        self.assertEqual(params, ("' OR '1'='1",))

    def test_returns_the_film(self):
        (store, _) = _store(results=[
            [('hash', 'Titel', 'Sendung', 'ARD', 'Text', 60, 0, '', 'u', '', '')],
        ])
        film = store.retrieve_film_info('hash')
        self.assertEqual(film.title, 'Titel')
        self.assertEqual(film.channel, 'ARD')

    def test_returns_none_when_the_film_is_gone(self):
        (store, _) = _store(results=[[]])
        self.assertIsNone(store.retrieve_film_info('missing'))


if __name__ == '__main__':
    unittest.main()
