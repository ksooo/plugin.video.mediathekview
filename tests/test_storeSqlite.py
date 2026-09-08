# -*- coding: utf-8 -*-
"""
Tests for the local SQLite store

SPDX-License-Identifier: MIT
"""

import shutil
import sqlite3
import tempfile
import unittest

from tests import support

support.init_app_context()

import resources.lib.appContext as appContext
from resources.lib.storeSqlite import StoreSQLite


class GivingUpAQueryTest(unittest.TestCase):
    """Letting go of a running query when Kodi wants the script gone.

    A query cannot be interrupted from outside, so a script sitting in one
    ignores Kodi's request to stop. Kodi then waits five seconds for it on its
    own main thread, rendering nothing and reading no input, before killing
    it - which is what a keypress during the database update runs into.
    """

    def setUp(self):
        self.datapath = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.datapath)
        self.monitor = support.Monitor()
        support.init_app_context(
            settings=support.Settings(datapath=self.datapath, caching=False),
            monitor=self.monitor)
        self.store = StoreSQLite()
        self.addCleanup(self.store.exit)
        self._fill()

    # What a listing runs: a scan with a condition, stepping row by row.
    LISTING = "SELECT idhash FROM film WHERE title LIKE '%Titel 1%'"

    def _fill(self):
        """A table big enough to run past the progress handler's interval."""
        connection = self.store.getConnection()
        connection.execute('CREATE TABLE film (idhash text, title text)')
        connection.executemany(
            'INSERT INTO film VALUES (?,?)',
            [(str(number), 'Titel %d' % number) for number in range(20000)])
        connection.commit()

    def test_a_query_runs_while_the_script_is_wanted(self):
        self.assertTrue(self.store.execute(self.LISTING))

    def test_a_query_gives_up_once_kodi_asks_the_script_to_stop(self):
        self.monitor.abort = True
        with self.assertRaises(sqlite3.OperationalError):
            self.store.execute(self.LISTING)

    def test_it_says_in_the_log_why_it_gave_up(self):
        self.monitor.abort = True
        try:
            self.store.execute(self.LISTING)
        except sqlite3.OperationalError:
            pass
        logged = [text for (level, text) in appContext.MVLOGGER.messages
                  if level == 'debug']
        self.assertTrue(any('giving up the running query' in text for text in logged),
                        logged)

    def test_it_says_it_only_once(self):
        self.monitor.abort = True
        for _ in range(2):
            try:
                self.store.execute(self.LISTING)
            except sqlite3.OperationalError:
                pass
        logged = [text for (level, text) in appContext.MVLOGGER.messages
                  if 'giving up' in text]
        self.assertEqual(len(logged), 1)

    def test_a_bare_count_cannot_be_given_up(self):
        # SQLite answers it with a single instruction inside the b-tree, so
        # the handler never gets a turn. No loss - that is the one query the
        # index covers, and nobody waits for it.
        self.monitor.abort = True
        self.assertEqual(self.store.execute('SELECT count(*) FROM film'), [(20000,)])

    def test_the_handler_answers_without_being_asked_to_stop(self):
        self.assertEqual(self.store._interruptWhenAborted(), 0)
        self.monitor.abort = True
        self.assertEqual(self.store._interruptWhenAborted(), 1)


if __name__ == '__main__':
    unittest.main()
