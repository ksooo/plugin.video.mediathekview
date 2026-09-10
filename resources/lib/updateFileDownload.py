# -*- coding: utf-8 -*-
"""
The database updater module

Copyright 2017-2019, Leo Moll and Dominik Schlösser
SPDX-License-Identifier: MIT
"""

# -- Imports ------------------------------------------------
import os
import time
import resources.lib.appContext as appContext

from urllib.error import URLError
from urllib.request import urlopen

from contextlib import closing
from codecs import open

import resources.lib.mvutils as mvutils

# from resources.lib.utils import *
from resources.lib.backgroundWork import run_in_background
from resources.lib.exceptions import ExitRequested

# -- Unpacker support ---------------------------------------
UPD_CAN_XZ = False
UPD_CAN_BZ2 = False
UPD_CAN_GZ = False

try:
    import lzma
    UPD_CAN_XZ = True
except ImportError:
    pass

try:
    import bz2
    UPD_CAN_BZ2 = True
except ImportError:
    pass

try:
    import gzip
    UPD_CAN_GZ = True
except ImportError:
    pass

# -- Constants ----------------------------------------------
FILMLISTE_URL = 'https://liste.mediathekview.de/'
# FILMLISTE_URL = 'http://192.168.137.100/content/'
# FILMLISTE_URL = 'http://192.168.137.100/content/test/'
FILMLISTE_AKT = 'Filmliste-akt'
FILMLISTE_DIF = 'Filmliste-diff'
DATABASE_URL = 'https://liste.mediathekview.de/'
# DATABASE_URL = 'http://192.168.137.100/content/'
# DATABASE_URL = 'http://192.168.137.100/content/test/'
DATABASE_DBF = 'filmliste-v3.db'
# DATABASE_AKT = 'filmliste-v2.db.update'
# Read this much at a time. Every chunk boundary is a trip back into python,
# and the interpreter lock is shared with the plugin the user is looking at.
COPY_BUFFER_SIZE = 1024 * 1024
# Write no faster than this. Unpacking bzip2 was slow enough to leave the
# storage some room by accident - some 9 MB/s on a Shield - and asking for
# gzip instead took that room away, which froze the interface for the whole
# update. Now the room is made on purpose. A job that runs once a day can
# afford to take twice as long.
WRITE_BYTES_PER_SEC = 10 * 1024 * 1024
# A result smaller than this is treated as truncated rather than as the real
# thing, because a truncated one used to wipe the database.
MINIMUM_SIZE = 200000000

# -- Classes ------------------------------------------------
# pylint: disable=bad-whitespace


class _CountingReader(object):
    """
    Counts what the unpacker has read, so progress has a denominator.

    The stream arrives from the network without a position of its own, and it
    is the compressed side whose total size the server announces.
    """

    def __init__(self, stream):
        self._stream = stream
        self.count = 0

    def read(self, size=-1):
        data = self._stream.read(size)
        self.count += len(data)
        return data

    def readable(self):
        return True

    def seekable(self):
        return False

    def close(self):
        pass


class UpdateFileDownload(object):
    """ The database updator class """

    def __init__(self):
        self.logger = appContext.MVLOGGER.get_new_logger('UpdateFileDownload')
        self.notifier = appContext.MVNOTIFIER
        self.settings = appContext.MVSETTINGS
        self.monitor = appContext.MVMONITOR
        self.database = None

    def getTargetFilename(self):
        return self._filename

    def removeDownloads(self):
        mvutils.file_remove(self._filename)

    def downloadIncrementalUpdateFile(self):
        self._filename = os.path.join(self.settings.getDatapath(), FILMLISTE_DIF)
        return self._download(FILMLISTE_URL + FILMLISTE_DIF + self._getExtension(),
                              self._filename)

    def downloadFullUpdateFile(self):
        self._filename = os.path.join(self.settings.getDatapath(), FILMLISTE_AKT)
        check = self._download(FILMLISTE_URL + FILMLISTE_AKT + self._getExtension(),
                               self._filename)
        if check:
            self._checkSize(self._filename)
        return check

    def downloadSqliteDb(self):
        self._filename = os.path.join(self.settings.getDatapath(), 'tmp_' + DATABASE_DBF)
        self._Dbfilename = os.path.join(self.settings.getDatapath(), DATABASE_DBF)
        check = self._download(DATABASE_URL + DATABASE_DBF + self._getExtension(),
                               self._filename)
        if check:
            self._checkSize(self._filename)
        return check

    def _checkSize(self, filename):
        """ A truncated download used to wipe the database, so refuse a small one """
        filesize = mvutils.file_size(filename)
        if filesize < MINIMUM_SIZE:
            raise Exception('FullUpdate file size {} smaller than allowed (200MB)'.format(filesize))

    def updateSqliteDb(self):
        start = time.time()
        mvutils.file_rename(self._filename, self._Dbfilename)
        self.logger.debug('renamed {} to {} in {} sec', self._filename, self._Dbfilename, (time.time() - start))

    def _getExtension(self):
        # Ordered by what unpacking costs, not by download size. Unpacking is
        # the part that competes with the interface, and measured on the real
        # archives gzip decompresses eleven times faster than bzip2 and six
        # times faster than xz. The archive is the largest of the three in
        # exchange - 150 MB against 113 - and it never reaches the disk.
        #
        # This used to look for an `xz` executable, which Kodi does not ship
        # while it does link liblzma, so every Kodi ended up on bzip2 - the
        # slowest of the three.
        if UPD_CAN_GZ is True:
            return '.gz'
        if UPD_CAN_XZ is True:
            return '.xz'
        if UPD_CAN_BZ2 is True:
            return '.bz2'
        self.logger.error('No suitable archive extractor available for this system')
        self.notifier.show_missing_extractor_error()
        return ""

    def _getReader(self, extension):
        """ The reader that unpacks the stream the given extension announces """
        if extension == '.gz':
            return lambda stream: gzip.GzipFile(fileobj=stream)
        if extension == '.xz':
            return lzma.LZMAFile
        if extension == '.bz2':
            return bz2.BZ2File
        raise Exception('No suitable archive extractor available for this system')

    def _download(self, url, targetFilename):
        start = time.time()
        mvutils.file_remove(targetFilename)
        self.notifier.show_download_progress()
        # pylint: disable=broad-except
        try:
            self.logger.debug('Downloading and unpacking {}', url)
            self.notifier.update_download_progress(0, url)
            written = run_in_background(
                lambda: self._retrieveUnpacked(url, targetFilename), name='Update')
            self.logger.debug('Wrote {} bytes in {} sec', written, (time.time() - start))
        except URLError as err:
            self.logger.error('Failure downloading {} - {}', url, err)
            self.notifier.close_download_progress()
            self.notifier.show_download_error(url, err)
            raise
        except ExitRequested as err:
            self.logger.error('Immediate exit requested. Aborting download of {}', url)
            self.notifier.close_download_progress()
            self.notifier.show_download_error(url, err)
            raise
        except Exception as err:
            self.logger.error('Failure downloading or unpacking {}: {}', url, err)
            self.notifier.close_download_progress()
            self.notifier.show_download_error(url, err)
            raise
        self.notifier.close_download_progress()
        return mvutils.file_exists(targetFilename)

    def _retrieveUnpacked(self, url, destfile):
        """
        Downloads and unpacks in one pass, writing only the result.

        Writing the archive out and reading it back cost the storage half again
        as much as the result itself - 758 MB of traffic for a 532 MB database,
        on the same flash the interface reads from. The archive therefore never
        reaches the disk, and there is no second phase to wait through.

        Progress is measured against the compressed side, which is the only
        total the server announces.
        """
        reader = self._getReader(self._getExtension())
        written = 0
        start = time.time()
        with closing(urlopen(url)) as response:
            counted = _CountingReader(response)
            totalsize = int(response.headers.get('Content-Length') or 0)
            with closing(reader(counted)) as srcfile, \
                    closing(open(destfile, 'wb')) as dstfile:
                shownPercent = -1
                while True:
                    if self.monitor.abort_requested():
                        raise ExitRequested('Download interrupted.')
                    data = srcfile.read(COPY_BUFFER_SIZE)
                    if not data:
                        break
                    dstfile.write(data)
                    written += len(data)
                    if totalsize > 0:
                        percent = int(counted.count * 100 / totalsize)
                        if percent != shownPercent:
                            shownPercent = percent
                            self.notifier.update_download_progress(percent)
                    # Hold the average down to the cap. Counting against
                    # everything written so far corrects itself, so a device
                    # slower than the cap never waits at all; waiting through
                    # the monitor rather than sleeping keeps an abort instant.
                    ahead = written / WRITE_BYTES_PER_SEC - (time.time() - start)
                    if ahead > 0 and self.monitor.wait_for_abort(ahead):
                        raise ExitRequested('Download interrupted.')
        return written
