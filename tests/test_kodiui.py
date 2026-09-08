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
UPDATE = 30956


class ProgressDialogTest(unittest.TestCase):
    """One dialog, two phases.

    The update downloads the film list and then imports it, and the dialog
    has to say which of the two is running rather than sitting at
    "downloading, 100%" through the second one.
    """

    def setUp(self):
        self.addon = support.Addon(strings={DOWNLOAD: 'Database update in progress',
                                            UPDATE: 'Mediathek Database Update'})
        support.init_app_context(addon=self.addon)
        self.dialog = KodiProgressDialog()

    def _shown(self):
        return support.progress_dialogs()[0]

    def test_the_first_phase_opens_the_dialog_with_its_heading(self):
        self.dialog.create(DOWNLOAD)
        self.assertEqual(self._shown().creates, [('Database update in progress', None)])

    def test_the_second_phase_keeps_the_dialog_and_changes_the_heading(self):
        self.dialog.create(DOWNLOAD)
        self.dialog.update(100)
        self.dialog.create(UPDATE, 'Filmliste-akt')
        self.assertEqual(len(support.progress_dialogs()), 1,
                         'the same dialog has to carry on')
        self.assertEqual(self._shown().updates[-1],
                         (0, 'Mediathek Database Update', 'Filmliste-akt'))

    def test_the_bar_goes_back_to_zero_for_the_second_phase(self):
        self.dialog.create(DOWNLOAD)
        self.dialog.update(100)
        self.dialog.create(UPDATE)
        (percent, _, _) = self._shown().updates[-1]
        self.assertEqual(percent, 0)

    def test_closing_lets_go_of_the_dialog(self):
        self.dialog.create(DOWNLOAD)
        self.dialog.close()
        self.assertTrue(self._shown().closed)
        self.assertIsNone(self.dialog.pgdialog)


if __name__ == '__main__':
    unittest.main()
