# -*- coding: utf-8 -*-
"""
Tests for the MySQL connection setup

SPDX-License-Identifier: MIT
"""

import unittest

from tests import support


class MySqlSettings(support.Settings):
    """The settings StoreMySQL asks for on top of the shared ones."""

    def getDatabaseHost(self):
        return 'db.example.org'

    def getDatabasePort(self):
        return 3306

    def getDatabaseUser(self):
        return 'mediathekview'

    def getDatabasePassword(self):
        return 'secret'

    def getDatabaseSchema(self):
        return 'mediathekview'


class Connection(support.Connection):

    def __init__(self, cursor_error=None, database_error=None):
        super(Connection, self).__init__()
        self.cursor_error = cursor_error
        self.database_error = database_error
        self._database = None

    def cursor(self):
        if self.cursor_error is not None:
            raise self.cursor_error
        return support.Connection.cursor(self)

    def _set_database(self, value):
        if self.database_error is not None:
            raise self.database_error
        self._database = value

    database = property(lambda self: self._database, _set_database)


def _store(connection):
    support.init_app_context(settings=MySqlSettings(caching=False))
    support.install_mysql_stub(lambda **kwargs: connection)
    from resources.lib.storeMySql import StoreMySQL
    return StoreMySQL()


class GetConnectionTest(unittest.TestCase):

    def test_a_failing_cursor_does_not_hide_behind_an_unbound_name(self):
        # cursor.close() used to sit outside the try that creates it, so a
        # server that refuses the cursor raised UnboundLocalError and buried
        # the real reason.
        connection = Connection(cursor_error=RuntimeError('server has gone away'))
        store = _store(connection)
        self.assertIs(store.getConnection(), connection)

    def test_selects_the_schema(self):
        connection = Connection()
        connection.results = [[('8.0.33',)]]
        store = _store(connection)
        store.getConnection()
        self.assertEqual(connection.database, 'mediathekview')

    def test_a_schema_that_cannot_be_selected_is_logged(self):
        connection = Connection(database_error=RuntimeError('unknown database'))
        connection.results = [[('8.0.33',)]]
        store = _store(connection)
        store.getConnection()
        import resources.lib.appContext as app_context
        logged = [text for (level, text) in app_context.MVLOGGER.messages
                  if level == 'error']
        self.assertTrue(any('unknown database' in text for text in logged), logged)

    def test_placeholders_are_translated_for_mysql(self):
        connection = Connection()
        connection.results = [[('8.0.33',)], []]
        store = _store(connection)
        store.execute('SELECT a FROM b WHERE c=? AND d=?', ('x', 'y'))
        self.assertIn('c=%s AND d=%s', connection.statements[-1])


if __name__ == '__main__':
    unittest.main()
