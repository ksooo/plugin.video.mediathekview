# -*- coding: utf-8 -*-
"""
Tests for running one long piece of work on a thread of its own

SPDX-License-Identifier: MIT
"""

import sys
import threading
import unittest

from tests import support

support.init_app_context()

import resources.lib.appContext as appContext
import resources.lib.backgroundWork as backgroundWork
from resources.lib.backgroundWork import run_in_background
from resources.lib.exceptions import ExitRequested


class RunInBackgroundTest(unittest.TestCase):
    """Handing the long work to a thread of its own.

    Downloading and unpacking half a gigabyte competes with whatever is
    drawing the interface. On a thread of its own it can be scheduled last,
    which is the one thing a script cannot arrange for the thread Kodi
    handed it.
    """

    def setUp(self):
        support.init_app_context()

    def test_it_hands_back_what_the_work_returned(self):
        self.assertEqual(run_in_background(lambda: 42), 42)

    def test_the_work_runs_on_another_thread(self):
        here = threading.get_ident()
        there = run_in_background(threading.get_ident)
        self.assertNotEqual(there, here)

    def test_the_name_reaches_the_thread(self):
        name = run_in_background(lambda: threading.current_thread().name, name='Unpack')
        self.assertEqual(name, 'Unpack')

    def test_it_waits_for_the_work_to_finish(self):
        done = []

        def work():
            for step in range(3):
                done.append(step)
            return 'finished'

        self.assertEqual(run_in_background(work), 'finished')
        self.assertEqual(done, [0, 1, 2])

    def test_nothing_is_left_running_afterwards(self):
        before = threading.active_count()
        run_in_background(lambda: None)
        self.assertEqual(threading.active_count(), before)

    def test_what_the_work_raised_is_raised_here(self):
        # The callers wrap this in their own error handling, and it has to
        # keep reading the same as when the work ran in line.
        def work():
            raise ExitRequested('Download interrupted.')

        with self.assertRaises(ExitRequested):
            run_in_background(work)

    def test_the_reason_survives(self):
        def work():
            raise RuntimeError('no space left on device')

        try:
            run_in_background(work)
            self.fail('the failure has to reach the caller')
        except RuntimeError as err:
            self.assertIn('no space left', str(err))


class StandAsideTest(unittest.TestCase):

    def setUp(self):
        support.init_app_context()
        self.logger = appContext.MVLOGGER.get_new_logger('test')

    def _logged(self):
        return [text for (level, text) in appContext.MVLOGGER.messages
                if level == 'debug']

    def test_the_worker_really_does_stand_aside(self):
        # Not a mock: the call either works on this system or it does not, and
        # a build where it silently does not is a build that measures nothing.
        run_in_background(lambda: None)
        logged = self._logged()
        self.assertTrue(any(text.startswith('Standing aside') for text in logged),
                        logged)

    def test_it_leaves_the_priority_alone_without_a_thread_id(self):
        # The process id is not a substitute: lowering that would take Kodi's
        # own threads down with it.
        if sys.platform == 'darwin':
            self.skipTest('darwin lowers the calling thread, it needs no thread id')
        previous = threading.get_native_id
        del threading.get_native_id
        self.addCleanup(setattr, threading, 'get_native_id', previous)
        backgroundWork._standAside(self.logger)
        self.assertTrue(any('cannot name its threads' in text for text in self._logged()),
                        self._logged())

    def test_a_refused_change_does_not_stop_the_work(self):
        def refuse(*args, **kwargs):
            raise OSError(1, 'not permitted')

        previous = backgroundWork.ctypes.CDLL
        backgroundWork.ctypes.CDLL = refuse
        self.addCleanup(setattr, backgroundWork.ctypes, 'CDLL', previous)
        self.assertEqual(run_in_background(lambda: 'done'), 'done')


if __name__ == '__main__':
    unittest.main()
