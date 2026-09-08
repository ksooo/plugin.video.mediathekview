# -*- coding: utf-8 -*-
"""
The database updater module

Copyright 2017-2019, Leo Moll and Dominik Schlösser
SPDX-License-Identifier: MIT
"""

# -- Imports ------------------------------------------------
import os
import shutil
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
# Read this much at a time while unpacking. The archive runs to hundreds of
# megabytes, and every chunk boundary is a trip back into Python, which holds
# up the plugin the user is looking at.
COPY_BUFFER_SIZE = 1024 * 1024
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
        # Ordered by what unpacking costs, not by download size. Unpacking is
        # the part that runs while the user waits, so the largest archive of
        # the three wins by being roughly ten times cheaper to unpack than
        # bzip2 and six times cheaper than xz.
        # Keep this in step with the chain in _download().
        ext = ""
        if UPD_CAN_GZ is True:
            ext = '.gz'
        elif self.use_xz is True or UPD_CAN_XZ is True:
            ext = '.xz'
        elif UPD_CAN_BZ2 is True:
            ext = '.bz2'
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
            mvutils.url_retrieve(
                url,
                filename=compressedFilename,
                reporthook=self.notifier.hook_download_progress,
                aborthook=self.monitor.abort_requested
            )
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
        start = time.time()
        try:
            # Mirrors the order in _getExtension(): whatever was asked for is
            # what arrived, and it has to be unpacked with the matching tool.
            if UPD_CAN_GZ is True:
                self.logger.debug('Trying to decompress gz file...')
                retval = self._decompress_gz(compressedFilename, targetFilename)
                self.logger.debug('decompress gz {} in {} sec', retval, (time.time() - start))
            elif self.use_xz is True:
                self.logger.debug('Trying to decompress xz file...')
                retval = subprocess.call([mvutils.find_xz(), '-d', compressedFilename])
                self.logger.debug('decompress xz {} in {} sec', retval, (time.time() - start))
            elif UPD_CAN_XZ is True:
                self.logger.debug('Trying to decompress xz file...')
                retval = self._decompress_xz(compressedFilename, targetFilename)
                self.logger.debug('decompress xz {} in {} sec', retval, (time.time() - start))
            elif UPD_CAN_BZ2 is True:
                self.logger.debug('Trying to decompress bz2 file...')
                retval = self._decompress_bz2(compressedFilename, targetFilename)
                self.logger.debug('decompress bz2 {} in {} sec', retval, (time.time() - start))
            else:
                # should never reach
                pass
        except Exception as err:
            self.logger.error('Failure decompress {}', err)
            self.notifier.close_download_progress()
            self.notifier.show_download_error('decompress failed', err)
            raise

        self.notifier.close_download_progress()
        return retval == 0 and mvutils.file_exists(targetFilename)

    def _decompress_xz(self, sourcefile, destfile):
        # pylint: disable=broad-except
        try:
            with closing(lzma.open(sourcefile, 'rb')) as srcfile, \
                    closing(open(destfile, 'wb')) as dstfile:
                shutil.copyfileobj(srcfile, dstfile, COPY_BUFFER_SIZE)
        except Exception as err:
            self.logger.error('xz decompression failed: {}', err)
            raise
        return 0

    def _decompress_bz2(self, sourcefile, destfile):
        blocksize = 8192
        try:
            with open(destfile, 'wb') as dstfile, open(sourcefile, 'rb') as srcfile:
                decompressor = bz2.BZ2Decompressor()
                for data in iter(lambda: srcfile.read(blocksize), b''):
                    dstfile.write(decompressor.decompress(data))
                # pylint: disable=broad-except
        except Exception as err:
            self.logger.error('bz2 decompression failed: {}'.format(err))
            raise
        return 0

    def _decompress_gz(self, sourcefile, destfile):
        # pylint: disable=broad-except
        try:
            with closing(gzip.open(sourcefile, 'rb')) as srcfile, \
                    closing(open(destfile, 'wb')) as dstfile:
                shutil.copyfileobj(srcfile, dstfile, COPY_BUFFER_SIZE)
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
