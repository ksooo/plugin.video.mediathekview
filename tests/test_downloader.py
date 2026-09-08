# -*- coding: utf-8 -*-
"""
Tests for the download helpers

SPDX-License-Identifier: MIT
"""

import unittest

from tests import support

support.init_app_context()

import xbmcvfs

from resources.lib.downloader import Downloader

_MESSAGE = 'Fehler beim Erzeugen des Download-Verzeichnisses: {}'


class EnsureDirectoryTest(unittest.TestCase):
    """xbmcvfs.mkdir() reports failure through its return value.

    It used to be called and ignored, so a directory that could not be
    created - no permission, a share that went away - let the download carry
    on and fail later with a message about the download instead.
    """

    def setUp(self):
        support.install_kodi_stubs()
        self.notifier = support.Notifier()
        support.init_app_context(notifier=self.notifier)
        self.plugin = support.Plugin(strings={30959: _MESSAGE})
        self.downloader = Downloader(self.plugin)
        self.created = []

    def _vfs(self, exists, mkdir_succeeds):
        xbmcvfs.exists = lambda path: exists
        def mkdir(path):
            self.created.append(path)
            return mkdir_succeeds
        xbmcvfs.mkdir = mkdir

    def test_an_existing_directory_is_left_alone(self):
        self._vfs(exists=True, mkdir_succeeds=True)
        self.assertTrue(self.downloader._ensure_directory('/downloads/show/'))
        self.assertEqual(self.created, [])
        self.assertEqual(self.notifier.errors, [])

    def test_a_missing_directory_is_created(self):
        self._vfs(exists=False, mkdir_succeeds=True)
        self.assertTrue(self.downloader._ensure_directory('/downloads/show/'))
        self.assertEqual(self.created, ['/downloads/show/'])
        self.assertEqual(self.notifier.errors, [])

    def test_a_failing_mkdir_stops_the_download(self):
        self._vfs(exists=False, mkdir_succeeds=False)
        self.assertFalse(self.downloader._ensure_directory('/downloads/show/'))

    def test_a_failing_mkdir_names_the_directory(self):
        self._vfs(exists=False, mkdir_succeeds=False)
        self.downloader._ensure_directory('/downloads/show/')
        self.assertEqual(len(self.notifier.errors), 1)
        (heading, message) = self.notifier.errors[0]
        self.assertEqual(heading, 30952)
        self.assertEqual(message, _MESSAGE.format('/downloads/show/'))


if __name__ == '__main__':
    unittest.main()
