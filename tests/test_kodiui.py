# -*- coding: utf-8 -*-
"""
Tests for the progress dialog

SPDX-License-Identifier: MIT
"""

import unittest

from tests import support

support.init_app_context()

from resources.lib.kodi.kodiui import KodiProgressDialog

DOWNLOAD = 30955
UNPACK = 30991


class ProgressDialogTest(unittest.TestCase):
    """One dialog, two phases.

    The update downloads and then unpacks, and the dialog has to say which of
    the two is running. Sitting at "downloading, 100%" through the unpacking
    is a dialog claiming to be finished with something else.
    """

    def setUp(self):
        self.addon = support.Addon(strings={DOWNLOAD: 'Download Database Update',
                                            UNPACK: 'Unpack Database Update'})
        support.init_app_context(addon=self.addon)
        self.dialog = KodiProgressDialog()

    def _shown(self):
        return support.progress_dialogs()[0]

    def test_the_first_phase_opens_the_dialog_with_its_heading(self):
        self.dialog.create(DOWNLOAD)
        self.assertEqual(self._shown().creates, [('Download Database Update', None)])

    def test_the_second_phase_keeps_the_dialog_and_changes_the_heading(self):
        self.dialog.create(DOWNLOAD)
        self.dialog.update(100)
        self.dialog.create(UNPACK, 'filmliste.bz2')
        self.assertEqual(len(support.progress_dialogs()), 1,
                         'the same dialog has to carry on')
        self.assertEqual(self._shown().updates[-1],
                         (0, 'Unpack Database Update', 'filmliste.bz2'))

    def test_the_bar_goes_back_to_zero_for_the_second_phase(self):
        self.dialog.create(DOWNLOAD)
        self.dialog.update(100)
        self.dialog.create(UNPACK)
        (percent, _, _) = self._shown().updates[-1]
        self.assertEqual(percent, 0)

    def test_closing_lets_go_of_the_dialog(self):
        self.dialog.create(DOWNLOAD)
        self.dialog.close()
        self.assertTrue(self._shown().closed)
        self.assertIsNone(self.dialog.pgdialog)


if __name__ == '__main__':
    unittest.main()
