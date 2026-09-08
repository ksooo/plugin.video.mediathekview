# -*- coding: utf-8 -*-
"""
Running one long piece of work on a thread of its own

SPDX-License-Identifier: MIT
"""

# -- Imports ------------------------------------------------
import ctypes
import sys
import threading

import resources.lib.appContext as appContext

# -- Constants ----------------------------------------------
# How often the waiting side looks whether the work has finished.
JOIN_SECONDS = 0.2
# How much to add to the worker's nice value, and how far that can go. From
# sys/resource.h; Linux applies these calls to a single thread when given a
# thread id, which is how Kodi lowers its own background threads.
NICE_INCREMENT = 10
NICE_MAX = 19
PRIO_PROCESS = 0
# Darwin has no nice value per thread. It has a background class instead,
# which covers the processor and the storage both, for the calling thread.
PRIO_DARWIN_THREAD = 3
PRIO_DARWIN_BG = 0x1000


# -- Functions ----------------------------------------------
def _standAside(logger):
    """
    Asks the system to schedule the calling thread behind everything else.

    Kodi lowers its own background threads exactly this way, but never the
    threads it hands to scripts. Until this call the unpacker competes with
    the thread drawing the interface as an equal.
    """
    # pylint: disable=broad-except
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        if sys.platform == 'darwin':
            _standAsideDarwin(libc, logger)
        else:
            _standAsidePosix(libc, logger)
    except Exception as err:
        # Not being allowed to stand aside is no reason not to do the work.
        logger.debug('Could not stand aside: {}', err)


def _standAsideDarwin(libc, logger):
    ctypes.set_errno(0)
    if libc.setpriority(PRIO_DARWIN_THREAD, 0, PRIO_DARWIN_BG) != 0:
        raise OSError(ctypes.get_errno(), 'setpriority failed')
    logger.debug('Standing aside in the background class')


def _standAsidePosix(libc, logger):
    nativeId = getattr(threading, 'get_native_id', None)
    if nativeId is None:
        # Without a thread id the only handle left would be the process, and
        # lowering that would take Kodi's own threads down with it.
        logger.debug('Could not stand aside: this python cannot name its threads')
        return
    threadId = nativeId()
    ctypes.set_errno(0)
    current = libc.getpriority(PRIO_PROCESS, threadId)
    if current == -1 and ctypes.get_errno() != 0:
        raise OSError(ctypes.get_errno(), 'getpriority failed')
    wanted = min(current + NICE_INCREMENT, NICE_MAX)
    if libc.setpriority(PRIO_PROCESS, threadId, wanted) != 0:
        raise OSError(ctypes.get_errno(), 'setpriority failed')
    logger.debug('Standing aside at nice {} instead of {}', wanted, current)


class _Worker(threading.Thread):
    """The thread the work actually runs on."""

    def __init__(self, work, name, logger):
        super(_Worker, self).__init__(name=name)
        # Kodi tears the interpreter down once the script ends; never hold
        # that up over work nobody is waiting for any more.
        self.daemon = True
        self._work = work
        self._logger = logger
        self.result = None
        self.error = None

    def run(self):
        _standAside(self._logger)
        # pylint: disable=broad-except
        try:
            self.result = self._work()
        except Exception as error:
            self.error = error


def run_in_background(work, name='UpdateWork'):
    """
    Runs `work` on a thread of its own and hands back what it returned.

    Downloading and unpacking half a gigabyte is the longest thing this addon
    does. On a thread of its own that work can ask to be scheduled last, which
    is the one thing a script cannot arrange for the thread Kodi gave it, and
    it leaves that thread free to answer while the work runs.

    Whatever the work raised is raised again here, so the caller's error
    handling reads the same as when the work ran in line.
    """
    logger = appContext.MVLOGGER.get_new_logger('BackgroundWork')
    worker = _Worker(work, name, logger)
    worker.start()
    while worker.is_alive():
        worker.join(JOIN_SECONDS)
    if worker.error is not None:
        raise worker.error
    return worker.result
