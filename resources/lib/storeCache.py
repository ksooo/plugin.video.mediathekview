# -*- coding: utf-8 -*-
"""
The query result cache

Copyright 2017-2019, Leo Moll
SPDX-License-Identifier: MIT
"""

# pylint: disable=too-many-lines,line-too-long

import os
import json
import time
import hashlib

from contextlib import closing
from codecs import open

import resources.lib.mvutils as mvutils
import resources.lib.appContext as appContext


class StoreCache(object):
    """
    Caches query results as JSON files, one per request type and condition.

    Everything cached here is void as soon as the film database is updated, so
    the whole directory is dropped by purge() when that happens.
    """

    CACHE_DIRECTORY = 'cache'

    def __init__(self):
        self.logger = appContext.MVLOGGER.get_new_logger('StoreCache')
        self.notifier = appContext.MVNOTIFIER
        self.settings = appContext.MVSETTINGS

    def _cacheDirectory(self):
        return os.path.join(self.settings.getDatapath(), self.CACHE_DIRECTORY)

    def _filename(self, reqtype, condition):
        # The condition holds whole SQL statements, so it is hashed rather
        # than used as a name. The file records it as well, and load_cache
        # compares it, so a collision cannot serve the wrong result.
        digest = hashlib.md5(condition.encode('utf-8')).hexdigest()[:16]
        return os.path.join(self._cacheDirectory(), '{}-{}.cache'.format(reqtype, digest))

    def load_cache(self, reqtype, condition):
        start = time.time()
        if not self.settings.getCaching():
            self.logger.debug('loading cache is disabled')
            return None
        #
        filename = self._filename(reqtype, condition)
        if not mvutils.file_exists(filename):
            self.logger.debug('no cache file request "{}" and condition "{}"', reqtype, condition)
            return None
        #
        dbLastUpdate = self.settings.getLastUpdate()
        try:
            with closing(open(filename, encoding='utf-8')) as json_file:
                data = json.load(json_file)
                if isinstance(data, dict):
                    if data.get('type', '') != reqtype:
                        self.logger.debug('no matching cache for type {} vs {}', data.get('type', ''), reqtype)
                        return None
                    if data.get('condition', '') != condition:
                        self.logger.debug('no matching cache for condition {} vs {}', data.get('condition', ''), condition)
                        return None
                    if int(dbLastUpdate) != data.get('time', 0):
                        self.logger.debug('outdated cache')
                        return None
                    data = data.get('data', [])
                    if isinstance(data, list):
                        self.logger.debug('return cache after {} sec for request "{}" and condition "{}"', (time.time() - start), reqtype, condition)
                        return data
        # pylint: disable=broad-except
        except Exception as err:
            # An unreadable cache file is not worth failing a query over: it
            # is gone by the time we return, and the caller reads the database.
            self.logger.error('Failed to load cache file {}: {}', filename, err)
            mvutils.file_remove(filename)
            return None
        self.logger.debug('no cache found')
        return None

    def save_cache(self, reqtype, condition, data):
        if not self.settings.getCaching():
            self.logger.debug('saving cache is disabled')
            return None
        if data is None:
            self.logger.debug('cache data is NONE')
            return None
        if len(data) == 0:
            self.logger.debug('no data to cache')
            return None
        if not isinstance(data, list):
            self.logger.debug('not a proper instance for caching')
            return None
        start = time.time()
        filename = self._filename(reqtype, condition)
        dbLastUpdate = self.settings.getLastUpdate()
        cache = {
            "type": reqtype,
            "time": int(dbLastUpdate),
            "condition": condition,
            "data": data
        }
        try:
            directory = self._cacheDirectory()
            if not os.path.exists(directory):
                os.makedirs(directory)
            with closing(open(filename, 'w', encoding='utf-8')) as json_file:
                json.dump(cache, json_file)
        # pylint: disable=broad-except
        except Exception as err:
            self.logger.error('Failed to write cache file {}: {}', filename, err)
            raise
        self.logger.debug('cache saved after {} sec for request "{}" and condition "{}"', (time.time() - start), reqtype, condition)

    def purge(self):
        """ Drops every cached result. To be called when the database changed """
        start = time.time()
        removed = 0
        directory = self._cacheDirectory()
        # pylint: disable=broad-except
        try:
            names = os.listdir(directory) if os.path.isdir(directory) else []
            for name in names:
                if name.endswith('.cache'):
                    mvutils.file_remove(os.path.join(directory, name))
                    removed += 1
            # Before the cache moved into its own directory it wrote one file
            # per request type next to the database.
            for name in os.listdir(self.settings.getDatapath()):
                if name.endswith('.cache'):
                    mvutils.file_remove(os.path.join(self.settings.getDatapath(), name))
                    removed += 1
        except Exception as err:
            self.logger.error('Failed to purge the cache: {}', err)
            return
        self.logger.debug('purged {} cache files in {} sec', removed, time.time() - start)
