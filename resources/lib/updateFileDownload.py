# -*- coding: utf-8 -*-
"""
The database updater module

Copyright 2017-2019, Leo Moll and Dominik Schlösser
SPDX-License-Identifier: MIT
"""

# -- Imports ------------------------------------------------
import os
import time
import subprocess
import resources.lib.appContext as appContext

# pylint: disable=import-error
try:
    # Python 3.x
    from urllib.error import URLError
except ImportError:
    # Python 2.x
    from urllib2 import URLError

from contextlib import closing
from codecs import open

import resources.lib.mvutils as mvutils

# from resources.lib.utils import *
from resources.lib.backgroundWork import run_in_background
from resources.lib.exceptions import ExitRequested

# -- Unpacker support ---------------------------------------
UPD_CAN_BZ2 = False
UPD_CAN_GZ = False

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

# -- Classes ------------------------------------------------
# pylint: disable=bad-whitespace


class UpdateFileDownload(object):
    """ The database updator class """

    def __init__(self):
        self.logger = appContext.MVLOGGER.get_new_logger('UpdateFileDownload')
        self.notifier = appContext.MVNOTIFIER
        self.settings = appContext.MVSETTINGS
        self.monitor = appContext.MVMONITOR
        self.database = None
        self.shownPercent = -1
        self.use_xz = mvutils.find_xz() is not None

    def getTargetFilename(self):
        return self._filename

    def removeDownloads(self):
        mvutils.file_remove(self._compressedFilename)
        mvutils.file_remove(self._filename)

    def downloadIncrementalUpdateFile(self):
        #
        ext = self._getExtension()
        downloadUrl = FILMLISTE_URL + FILMLISTE_DIF + ext
        self._compressedFilename = os.path.join(self.settings.getDatapath() , FILMLISTE_DIF + ext)
        self._filename = os.path.join(self.settings.getDatapath() , FILMLISTE_DIF)
        #
        check = self._download(downloadUrl, self._compressedFilename, self._filename)
        #
        return check

    def downloadFullUpdateFile(self):
        #
        ext = self._getExtension()
        downloadUrl = FILMLISTE_URL + FILMLISTE_AKT + ext
        self._compressedFilename = os.path.join(self.settings.getDatapath() , FILMLISTE_AKT + ext)
        self._filename = os.path.join(self.settings.getDatapath() , FILMLISTE_AKT)
        #
        check = self._download(downloadUrl, self._compressedFilename, self._filename)
        #
        if check:
            filesize = mvutils.file_size(self._filename)
            if filesize < 200000000:
                raise Exception('FullUpdate file size {} smaller than allowed (200MB)'.format(filesize))
        #
        return check

    def downloadSqliteDb(self):
        ext = self._getExtension()
        downloadUrl = DATABASE_URL + DATABASE_DBF + ext
        self._compressedFilename = os.path.join(self.settings.getDatapath() , 'tmp_' + DATABASE_DBF + ext)
        self._filename = os.path.join(self.settings.getDatapath() , 'tmp_' + DATABASE_DBF)
        self._Dbfilename = os.path.join(self.settings.getDatapath() , DATABASE_DBF)

        #
        check = self._download(downloadUrl, self._compressedFilename, self._filename)
        #
        if check:
            filesize = mvutils.file_size(self._filename)
            if filesize < 200000000:
                raise Exception('FullUpdate file size {} smaller than allowed (200MB)'.format(filesize))
        #
        return check

    def updateSqliteDb(self):
        start = time.time()
        mvutils.file_rename(self._filename, self._Dbfilename)
        self.logger.debug('renamed {} to {} in {} sec', self._filename, self._Dbfilename, (time.time() - start))

    def _getExtension(self):
        ext = ""
        if self.use_xz is True:
            ext = '.xz'
        elif UPD_CAN_BZ2 is True:
            ext = '.bz2'
        elif UPD_CAN_GZ is True:
            ext = '.gz'
        else:
            self.logger.error('No suitable archive extractor available for this system')
            self.notifier.show_missing_extractor_error()
        return ext

    def _download(self, url, compressedFilename, targetFilename):
        # cleanup downloads
        start = time.time()
        self.logger.debug('Cleaning up old downloads...')
        mvutils.file_remove(compressedFilename)
        mvutils.file_remove(targetFilename)
        #
        # download filmliste
        self.notifier.show_download_progress()

        # pylint: disable=broad-except
        try:
            self.logger.debug('Trying to download {} from {}...',
                             os.path.basename(compressedFilename), url)
            self.notifier.update_download_progress(0, url)
            run_in_background(lambda: mvutils.url_retrieve(
                url,
                filename=compressedFilename,
                reporthook=self.notifier.hook_download_progress,
                aborthook=self.monitor.abort_requested
            ), name='Download')
            self.logger.debug('downloaded {} in {} sec', compressedFilename, (time.time() - start))
        except URLError as err:
            self.logger.error('Failure downloading {} - {}', url, err)
            self.notifier.close_download_progress()
            self.notifier.show_download_error(url, err)
            raise
        except ExitRequested as err:
            self.logger.error(
                'Immediate exit requested. Aborting download of {}', url)
            self.notifier.close_download_progress()
            self.notifier.show_download_error(url, err)
            raise
        except Exception as err:
            self.logger.error('Failure writing {}', url)
            self.notifier.close_download_progress()
            self.notifier.show_download_error(url, err)
            raise
        # decompress filmliste
        try:
            retval = run_in_background(
                lambda: self._decompress(compressedFilename, targetFilename, url),
                name='Unpack')
        except Exception as err:
            self.logger.error('Failure decompress {}', err)
            self.notifier.close_download_progress()
            self.notifier.show_download_error('decompress failed', err)
            raise

        self.notifier.close_download_progress()
        return retval == 0 and mvutils.file_exists(targetFilename)

    def _decompress(self, compressedFilename, targetFilename, sourceUrl=None):
        """ Unpacks with the tool that matches what _getExtension() asked for """
        start = time.time()
        self.shownPercent = -1
        # The dialog keeps saying where the update came from; only the heading
        # and the bar change. The name on disk is the download's own scratch
        # file and means nothing to anybody.
        self.notifier.show_unpack_progress(sourceUrl)
        if self.use_xz is True:
            self.logger.debug('Trying to decompress xz file...')
            retval = subprocess.call([mvutils.find_xz(), '-d', compressedFilename])
            self.logger.debug('decompress xz {} in {} sec', retval, (time.time() - start))
        elif UPD_CAN_BZ2 is True:
            self.logger.debug('Trying to decompress bz2 file...')
            retval = self._decompress_bz2(compressedFilename, targetFilename)
            self.logger.debug('decompress bz2 {} in {} sec', retval, (time.time() - start))
        elif UPD_CAN_GZ is True:
            self.logger.debug('Trying to decompress gz file...')
            retval = self._decompress_gz(compressedFilename, targetFilename)
            self.logger.debug('decompress gz {} in {} sec', retval, (time.time() - start))
        else:
            # _getExtension() has already reported this and asked for nothing,
            # so there is nothing to unpack.
            retval = 1
        return retval

    def _reportUnpackProgress(self, read, total):
        """
        Moves the bar, but only when the number on it changes.

        The unpacking reads in 8 KB blocks, so a hundred megabytes would
        otherwise ask for twelve thousand repaints.
        """
        if total <= 0:
            return
        percent = int(read * 100 / total)
        if percent != self.shownPercent:
            self.shownPercent = percent
            self.notifier.update_unpack_progress(percent)

    def _decompress_bz2(self, sourcefile, destfile):
        blocksize = 8192
        total = mvutils.file_size(sourcefile)
        read = 0
        try:
            with open(destfile, 'wb') as dstfile, open(sourcefile, 'rb') as srcfile:
                decompressor = bz2.BZ2Decompressor()
                for data in iter(lambda: srcfile.read(blocksize), b''):
                    dstfile.write(decompressor.decompress(data))
                    read += len(data)
                    self._reportUnpackProgress(read, total)
                # pylint: disable=broad-except
        except Exception as err:
            self.logger.error('bz2 decompression failed: {}'.format(err))
            raise
        return 0

    def _decompress_gz(self, sourcefile, destfile):
        blocksize = 8192
        total = mvutils.file_size(sourcefile)
        # pylint: disable=broad-except

        try:
            # Read through a handle of our own: how far the compressed side
            # has come is what the progress can be measured against.
            with open(destfile, 'wb') as dstfile, open(sourcefile, 'rb') as rawfile:
                with gzip.GzipFile(fileobj=rawfile) as srcfile:
                    for data in iter(lambda: srcfile.read(blocksize), b''):
                        dstfile.write(data)
                        self._reportUnpackProgress(rawfile.tell(), total)
        except Exception as err:
            self.logger.error(
                'gz decompression of "{}" to "{}" failed: {}', sourcefile, destfile, err)
            if mvutils.find_gzip() is not None:
                gzip_binary = mvutils.find_gzip()
                self.logger.debug(
                    'Trying to decompress gzip file "{}" using {}...', sourcefile, gzip_binary)
                try:
                    mvutils.file_remove(destfile)
                    retval = subprocess.call([gzip_binary, '-d', sourcefile])
                    self.logger.debug('Calling {} -d {} returned {}',
                                     gzip_binary, sourcefile, retval)
                    return retval
                except Exception as err:
                    self.logger.error(
                        'gz commandline decompression of "{}" to "{}" failed: {}',
                        sourcefile, destfile, err)
            raise
        return 0
