# -*- coding: utf-8 -*-
"""
Tests for downloading and unpacking the film database

SPDX-License-Identifier: MIT
"""

import bz2
import gzip
import io
import lzma
import os
import shutil
import tempfile
import unittest

from tests import support

support.init_app_context()

import resources.lib.appContext as appContext
import resources.lib.updateFileDownload as updateFileDownload
from resources.lib.exceptions import ExitRequested
from resources.lib.updateFileDownload import UpdateFileDownload

_PAYLOAD = b'{"Filmliste":["30.08.2020, 11:13"]}\n' * 4096


class _Response(io.BytesIO):
    """Stands in for what urlopen returns."""

    def __init__(self, data, length=None):
        super(_Response, self).__init__(data)
        announced = len(data) if length is None else length
        self.headers = {'Content-Length': str(announced)}


def _serve(data, length=None):
    """Makes urlopen hand out the given bytes, and reports what was asked for."""
    asked = []

    def urlopen(url, *args, **kwargs):
        asked.append(url)
        return _Response(data, length)

    updateFileDownload.urlopen = urlopen
    return asked


class ExtensionTest(unittest.TestCase):
    """Which archive the addon asks the server for.

    Ordered by what unpacking costs rather than by download size: gzip first,
    then xz, then bzip2. Measured on the real archives, gzip decompresses
    eleven times faster than bzip2 and six times faster than xz, at the price
    of 150 MB against 113. Kodi ships liblzma but no xz executable, and the
    choice used to look for the executable, which sent every Kodi to bzip2 -
    the slowest of the three.
    """

    def setUp(self):
        support.init_app_context()
        self.download = UpdateFileDownload()

    def test_gz_is_the_first_choice(self):
        self.assertEqual(self.download._getExtension(), '.gz')

    def test_falls_back_to_xz_without_gzip(self):
        self._without('UPD_CAN_GZ')
        self.assertEqual(self.download._getExtension(), '.xz')

    def test_falls_back_to_bz2_without_gzip_and_lzma(self):
        self._without('UPD_CAN_GZ')
        self._without('UPD_CAN_XZ')
        self.assertEqual(self.download._getExtension(), '.bz2')

    def test_every_extension_has_a_reader(self):
        for (extension, packer) in (('.gz', gzip), ('.xz', lzma), ('.bz2', bz2)):
            reader = self.download._getReader(extension)
            stream = io.BytesIO(packer.compress(_PAYLOAD))
            self.assertEqual(reader(stream).read(), _PAYLOAD, extension)

    def _without(self, name):
        previous = getattr(updateFileDownload, name)
        setattr(updateFileDownload, name, False)
        self.addCleanup(setattr, updateFileDownload, name, previous)


class RetrieveUnpackedTest(unittest.TestCase):
    """Downloading and unpacking in one pass.

    The archive used to be written out and read back, which cost the storage
    758 MB of traffic for a 532 MB database, on the same flash the interface
    reads from.
    """

    def setUp(self):
        self.notifier = support.Notifier()
        self.monitor = support.Monitor()
        support.init_app_context(notifier=self.notifier, monitor=self.monitor)
        self.download = UpdateFileDownload()
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory)
        self.target = os.path.join(self.directory, 'filmliste')
        self._urlopen = updateFileDownload.urlopen
        self.addCleanup(setattr, updateFileDownload, 'urlopen', self._urlopen)

    def test_writes_the_unpacked_result(self):
        _serve(gzip.compress(_PAYLOAD))
        written = self.download._retrieveUnpacked('https://example.org/x.gz', self.target)
        self.assertEqual(written, len(_PAYLOAD))
        with open(self.target, 'rb') as handle:
            self.assertEqual(handle.read(), _PAYLOAD)

    def test_the_archive_never_reaches_the_disk(self):
        _serve(gzip.compress(_PAYLOAD))
        self.download._retrieveUnpacked('https://example.org/x.gz', self.target)
        self.assertEqual(os.listdir(self.directory), ['filmliste'])

    def test_asks_for_the_url_it_was_given(self):
        asked = _serve(gzip.compress(_PAYLOAD))
        self.download._retrieveUnpacked('https://example.org/x.gz', self.target)
        self.assertEqual(asked, ['https://example.org/x.gz'])

    def test_a_result_larger_than_the_buffer_arrives_whole(self):
        payload = _PAYLOAD * 32
        self.assertGreater(len(payload), updateFileDownload.COPY_BUFFER_SIZE)
        _serve(gzip.compress(payload))
        self.download._retrieveUnpacked('https://example.org/x.gz', self.target)
        self.assertEqual(os.path.getsize(self.target), len(payload))

    def test_concatenated_gzip_members_arrive_whole(self):
        _serve(gzip.compress(b'first ') + gzip.compress(b'second'))
        self.download._retrieveUnpacked('https://example.org/x.gz', self.target)
        with open(self.target, 'rb') as handle:
            self.assertEqual(handle.read(), b'first second')

    def test_a_truncated_archive_raises(self):
        _serve(gzip.compress(_PAYLOAD)[:64])
        with self.assertRaises(Exception):
            self.download._retrieveUnpacked('https://example.org/x.gz', self.target)

    def test_an_abort_stops_it(self):
        _serve(gzip.compress(_PAYLOAD))
        self.monitor.abort = True
        with self.assertRaises(ExitRequested):
            self.download._retrieveUnpacked('https://example.org/x.gz', self.target)

    def test_reports_progress_against_the_announced_size(self):
        _serve(gzip.compress(_PAYLOAD * 32))
        self.download._retrieveUnpacked('https://example.org/x.gz', self.target)
        self.assertTrue(self.notifier.progress, 'the bar has to move')
        self.assertEqual(self.notifier.progress, sorted(self.notifier.progress))
        self.assertLessEqual(max(self.notifier.progress), 100)

    def test_the_progress_is_only_reported_when_it_changes(self):
        _serve(gzip.compress(_PAYLOAD * 32))
        self.download._retrieveUnpacked('https://example.org/x.gz', self.target)
        self.assertEqual(len(self.notifier.progress),
                         len(set(self.notifier.progress)))

    def test_an_unannounced_size_reports_no_progress(self):
        _serve(gzip.compress(_PAYLOAD), length=0)
        self.download._retrieveUnpacked('https://example.org/x.gz', self.target)
        self.assertEqual(self.notifier.progress, [])

    def test_the_result_is_logged(self):
        _serve(gzip.compress(_PAYLOAD))
        self.download._download('https://example.org/x.gz', self.target)
        logged = [text for (level, text) in appContext.MVLOGGER.messages
                  if level == 'debug']
        self.assertTrue(any('Wrote' in text for text in logged), logged)


class WriteRateTest(unittest.TestCase):
    """How fast the result is allowed to be written.

    Unpacking bzip2 was slow enough to leave the storage some room by
    accident. Asking for gzip instead took that room away and froze the
    interface for the whole update, so the room is now made on purpose.
    """

    def setUp(self):
        self.notifier = support.Notifier()
        self.monitor = support.Monitor()
        support.init_app_context(notifier=self.notifier, monitor=self.monitor)
        self.download = UpdateFileDownload()
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory)
        self.target = os.path.join(self.directory, 'filmliste')
        self.addCleanup(setattr, updateFileDownload, 'urlopen',
                        updateFileDownload.urlopen)
        self.waits = []
        self.monitor.wait_for_abort = lambda seconds: self.waits.append(seconds) or False

    def _cap(self, bytesPerSecond):
        self.addCleanup(setattr, updateFileDownload, 'WRITE_BYTES_PER_SEC',
                        updateFileDownload.WRITE_BYTES_PER_SEC)
        updateFileDownload.WRITE_BYTES_PER_SEC = bytesPerSecond

    def _retrieve(self):
        _serve(gzip.compress(_PAYLOAD))
        return self.download._retrieveUnpacked('https://example.org/x.gz', self.target)

    def test_it_holds_back_when_it_is_ahead_of_the_cap(self):
        self._cap(1024)
        self._retrieve()
        # 143 KB at 1 KB/s is well over a minute of holding back.
        self.assertTrue(self.waits, 'it has to hold back')
        self.assertGreater(sum(self.waits), 100)

    def test_a_device_slower_than_the_cap_never_holds_back(self):
        self._cap(1024 ** 4)
        self._retrieve()
        self.assertEqual(self.waits, [])

    def test_holding_back_does_not_change_the_result(self):
        self._cap(1024)
        written = self._retrieve()
        self.assertEqual(written, len(_PAYLOAD))
        with open(self.target, 'rb') as handle:
            self.assertEqual(handle.read(), _PAYLOAD)

    def test_an_abort_while_holding_back_stops_it(self):
        self._cap(1024)
        self.monitor.wait_for_abort = lambda seconds: True
        with self.assertRaises(ExitRequested):
            self._retrieve()


class SizeCheckTest(unittest.TestCase):

    def setUp(self):
        support.init_app_context()
        self.download = UpdateFileDownload()
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory)

    def _file(self, size):
        path = os.path.join(self.directory, 'filmliste')
        with open(path, 'wb') as handle:
            handle.write(b'x' * size)
        return path

    def test_a_full_sized_result_passes(self):
        previous = updateFileDownload.MINIMUM_SIZE
        updateFileDownload.MINIMUM_SIZE = 16
        self.addCleanup(setattr, updateFileDownload, 'MINIMUM_SIZE', previous)
        self.download._checkSize(self._file(32))

    def test_a_truncated_result_is_refused(self):
        # A short download used to be put in place and wipe the database.
        with self.assertRaises(Exception):
            self.download._checkSize(self._file(1024))


if __name__ == '__main__':
    unittest.main()
