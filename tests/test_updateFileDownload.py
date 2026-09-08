# -*- coding: utf-8 -*-
"""
Tests for choosing and running the archive extractor

SPDX-License-Identifier: MIT
"""

import bz2
import lzma
import os
import shutil
import tempfile
import unittest

from tests import support

support.init_app_context()

import resources.lib.updateFileDownload as updateFileDownload
from resources.lib.updateFileDownload import UpdateFileDownload

_PAYLOAD = b'{"Filmliste":["30.08.2020, 11:13"]}\n' * 4096


class ExtensionTest(unittest.TestCase):
    """Which archive the addon asks the server for.

    Kodi links its Python against liblzma but ships no xz executable - the
    xz build turns the command line tools off. Looking for the binary alone
    therefore sent every such platform, Android among them, to bz2, which is
    both the largest download here and the slowest to unpack.
    """

    def setUp(self):
        support.init_app_context()
        self.download = UpdateFileDownload()

    def test_xz_without_the_binary(self):
        self.download.use_xz = False
        self.assertEqual(self.download._getExtension(), '.xz')

    def test_xz_with_the_binary(self):
        self.download.use_xz = True
        self.assertEqual(self.download._getExtension(), '.xz')

    def test_falls_back_to_bz2_without_lzma(self):
        self.download.use_xz = False
        self._without('UPD_CAN_XZ')
        self.assertEqual(self.download._getExtension(), '.bz2')

    def test_falls_back_to_gz_without_lzma_and_bz2(self):
        self.download.use_xz = False
        self._without('UPD_CAN_XZ')
        self._without('UPD_CAN_BZ2')
        self.assertEqual(self.download._getExtension(), '.gz')

    def _without(self, name):
        previous = getattr(updateFileDownload, name)
        setattr(updateFileDownload, name, False)
        self.addCleanup(setattr, updateFileDownload, name, previous)


class DecompressTest(unittest.TestCase):

    def setUp(self):
        support.init_app_context()
        self.download = UpdateFileDownload()
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory)

    def _paths(self, suffix):
        return (os.path.join(self.directory, 'archive' + suffix),
                os.path.join(self.directory, 'archive'))

    def test_unpacks_an_xz_archive(self):
        (source, target) = self._paths('.xz')
        with lzma.open(source, 'wb') as handle:
            handle.write(_PAYLOAD)
        self.assertEqual(self.download._decompress_xz(source, target), 0)
        with open(target, 'rb') as handle:
            self.assertEqual(handle.read(), _PAYLOAD)

    def test_unpacks_an_archive_larger_than_the_buffer(self):
        payload = _PAYLOAD * 32
        self.assertGreater(len(payload), updateFileDownload.COPY_BUFFER_SIZE)
        (source, target) = self._paths('.xz')
        with lzma.open(source, 'wb') as handle:
            handle.write(payload)
        self.download._decompress_xz(source, target)
        self.assertEqual(os.path.getsize(target), len(payload))

    def test_a_truncated_archive_raises(self):
        (source, target) = self._paths('.xz')
        with lzma.open(source, 'wb') as handle:
            handle.write(_PAYLOAD)
        with open(source, 'rb') as handle:
            broken = handle.read()[:64]
        with open(source, 'wb') as handle:
            handle.write(broken)
        with self.assertRaises(Exception):
            self.download._decompress_xz(source, target)

    def test_bz2_still_works(self):
        (source, target) = self._paths('.bz2')
        with bz2.open(source, 'wb') as handle:
            handle.write(_PAYLOAD)
        self.assertEqual(self.download._decompress_bz2(source, target), 0)
        with open(target, 'rb') as handle:
            self.assertEqual(handle.read(), _PAYLOAD)


if __name__ == '__main__':
    unittest.main()
