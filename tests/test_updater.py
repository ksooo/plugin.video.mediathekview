# -*- coding: utf-8 -*-
"""
Tests for when the updater is allowed to start

SPDX-License-Identifier: MIT
"""

import unittest

from tests import support

support.init_app_context()
# Importing the updater reaches storeMySql, and through it mysql.connector,
# which Kodi supplies as script.module.myconnpy and the tests do not have.
support.install_mysql_stub(lambda **kwargs: None)

import resources.lib.appContext as appContext
from resources.lib.updater import MediathekViewUpdater, UNATTENDED_IDLE_SEC


class Monitor(support.Monitor):

    def __init__(self, idle=0, playing=False):
        super(Monitor, self).__init__()
        self.idle = idle
        self.playing = playing

    def get_idle_time(self):
        return self.idle

    def is_playing(self):
        return self.playing


class IsKodiUnattendedTest(unittest.TestCase):
    """The automatic update is allowed once Kodi has been left alone.

    It requires recent use of the add-on, which saves bandwidth on
    installations that never open it - but that made the update start
    because the user opened the add-on, and then compete with them.
    """

    def _updater(self, **kwargs):
        support.init_app_context(monitor=Monitor(**kwargs))
        return MediathekViewUpdater()

    def test_waits_while_kodi_is_being_used(self):
        updater = self._updater(idle=0)
        self.assertFalse(updater.isKodiUnattended())

    def test_waits_until_the_threshold_is_reached(self):
        updater = self._updater(idle=UNATTENDED_IDLE_SEC - 1)
        self.assertFalse(updater.isKodiUnattended())

    def test_runs_once_kodi_has_been_left_alone(self):
        updater = self._updater(idle=UNATTENDED_IDLE_SEC)
        self.assertTrue(updater.isKodiUnattended())

    def test_playback_counts_as_use_however_idle_the_input(self):
        # Watching produces no input at all, so the idle time grows while the
        # one moment an update hurts most is going on.
        updater = self._updater(idle=3600, playing=True)
        self.assertFalse(updater.isKodiUnattended())

    def test_says_why_it_waits(self):
        updater = self._updater(idle=0)
        updater.isKodiUnattended()
        messages = [text for (_, text) in appContext.MVLOGGER.messages]
        self.assertTrue(any('Postponing' in text for text in messages), messages)


if __name__ == '__main__':
    unittest.main()
