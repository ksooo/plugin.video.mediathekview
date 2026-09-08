# -*- coding: utf-8 -*-
"""
The local SQlite database module

Copyright 2017-2019, Leo Moll
SPDX-License-Identifier: MIT
"""

# pylint: disable=too-many-lines,line-too-long
import os
import time
import sqlite3
import resources.lib.mvutils as mvutils
import resources.lib.appContext as appContext
from resources.lib.storeQuery import StoreQuery

# -- Constants ----------------------------------------------
# How many SQLite instructions between two checks whether this script is
# still supposed to be running. A row costs some five instructions, so a scan
# of the film table asks a few thousand times - nothing next to the scan, and
# often enough to let go the moment Kodi says so.
#
# Only statements that step through the virtual machine can be given up this
# way. A bare `SELECT count(*)` is a single instruction inside the b-tree and
# runs to the end regardless, which is no loss: it is the one query answered
# from the index, and nobody waits for it.
PROGRESS_HANDLER_INSTRUCTIONS = 1000


class StoreSQLite(StoreQuery):
    """
    The local SQlite database class

    """

    def __init__(self):
        super(StoreSQLite, self).__init__()
        self.logger = appContext.MVLOGGER.get_new_logger('StoreSQLite')
        self.notifier = appContext.MVNOTIFIER
        self.settings = appContext.MVSETTINGS
        self.monitor = appContext.MVMONITOR
        self.databaseFilename = 'filmliste-v3.db'
        # internals
        self.conn = None
        self._interrupted = False
        self.dbfile = os.path.join(self.settings.getDatapath(), self.databaseFilename)
        self.logger.debug('StoreSQLite DBFile: {}', self.dbfile)

    def getConnection(self):
        if self.conn is None:
            if (not mvutils.file_exists(self.dbfile)):
                self.settings.setDatabaseStatus('UNINIT')
                self.logger.debug('Missing StoreSQLite DBFile: {}', self.dbfile)
            self.conn = sqlite3.connect(self.dbfile, timeout=60)
            self.conn.execute('pragma synchronous=off')
            self.conn.execute('pragma journal_mode=off')
            self.conn.execute('pragma page_size=16384')
            self.conn.execute('pragma encoding="UTF-8"')
            self.conn.set_progress_handler(self._interruptWhenAborted,
                                           PROGRESS_HANDLER_INSTRUCTIONS)
        return self.conn

    def _interruptWhenAborted(self):
        """
        Lets SQLite give up a running statement when Kodi wants us gone.

        A query cannot be interrupted from outside, so a script sitting in one
        ignores the request to stop. Kodi then waits five seconds for it on its
        own main thread, rendering nothing and reading no input, before killing
        it - which is what a keypress during the database update runs into.
        """
        if not self.monitor.abort_requested():
            return 0
        if not self._interrupted:
            self._interrupted = True
            self.logger.debug('Kodi asked this script to stop, giving up the running query')
        return 1

    def exit(self):
        if self.conn is not None:
            self.conn.commit()
            self.conn.close()
            self.conn = None

    def reset(self):
        mvutils.file_remove(self.dbfile)
        # last version
        mvutils.file_remove(os.path.join(self.settings.getDatapath(), 'filmliste-v2.db'))
        self.conn = None

    # ABSTRACT
    def getDatabaseStatus(self):
        updateStatus = {
            'lastUpdate': self.settings.getLastUpdate(),
            'status': self.settings.getDatabaseStatus(),
            'lastFullUpdate': self.settings.getLastFullUpdate(),
            'version': self.settings.getDatabaseVersion()
        }
        return updateStatus
