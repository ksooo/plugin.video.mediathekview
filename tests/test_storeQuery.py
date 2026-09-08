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


if __name__ == '__main__':
    unittest.main()
