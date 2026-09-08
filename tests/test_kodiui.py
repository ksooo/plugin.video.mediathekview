# -*- coding: utf-8 -*-
"""
Tests for the progress dialog

SPDX-License-Identifier: MIT
"""

import unittest

from tests import support

support.init_app_context()

from resources.lib.kodi.kodiui import KodiProgressDialog

_CHUNK = 65536


class UrlRetrieveHookTest(unittest.TestCase):
    """The hook mvutils.url_retrieve calls once per chunk.

    A few hundred megabytes at 64 KB a chunk is thousands of calls, and each
    one crosses from the service thread into the GUI. Only a changed whole
    percentage is worth that.
    """

    def setUp(self):
        support.init_app_context()
        self.dialog = KodiProgressDialog()
        self.dialog.create('Downloading')
        self.updates = support._DialogProgressBG.instances[-1].updates
        self.updates.clear()

    def _download(self, total):
        chunks = total // _CHUNK
        for count in range(chunks):
            self.dialog.url_retrieve_hook(count, _CHUNK, total)

    def test_reports_every_percentage_once(self):
        self._download(400 * 1024 * 1024)
        self.assertEqual(self.updates, sorted(set(self.updates)))
        self.assertEqual(len(self.updates), len(set(self.updates)))

    def test_never_repaints_more_than_a_hundred_times(self):
        self._download(400 * 1024 * 1024)
        self.assertLessEqual(len(self.updates), 100)

    def test_still_reaches_the_end(self):
        self._download(400 * 1024 * 1024)
        self.assertEqual(self.updates[0], 0)
        self.assertEqual(self.updates[-1], 99)

    def test_a_small_download_reports_every_step(self):
        self._download(10 * _CHUNK)
        self.assertEqual(self.updates, [0, 10, 20, 30, 40, 50, 60, 70, 80, 90])

    def test_an_unknown_total_size_reports_nothing(self):
        self.dialog.url_retrieve_hook(1, _CHUNK, 0)
        self.assertEqual(self.updates, [])

    def test_a_second_download_starts_over(self):
        self._download(10 * _CHUNK)
        self.dialog.create('Downloading again')
        self.updates.clear()
        self.dialog.url_retrieve_hook(0, _CHUNK, 10 * _CHUNK)
        self.assertEqual(self.updates, [0])


if __name__ == '__main__':
    unittest.main()
