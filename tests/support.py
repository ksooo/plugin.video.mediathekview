# -*- coding: utf-8 -*-
"""
Fixtures for testing the addon outside Kodi

SPDX-License-Identifier: MIT
"""

import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_KODI_MODULES = ('xbmc', 'xbmcaddon', 'xbmcgui', 'xbmcplugin', 'xbmcvfs')


def install_kodi_stubs():
    """Registers empty stand-ins for the Kodi modules.

    Deliberately not done on import: mvutils decides on ``import xbmcvfs``
    whether it is running inside Kodi, so a stub that is always present would
    silently send it down the Kodi path. Only tests that need the stubs ask
    for them.
    """
    for name in _KODI_MODULES:
        sys.modules.setdefault(name, types.ModuleType(name))


class Logger(object):
    """Collects log calls instead of writing them anywhere."""

    def __init__(self):
        self.messages = []

    def _record(self, level, message, *args):
        self.messages.append((level, message.format(*args) if args else message))

    def debug(self, message, *args):
        self._record('debug', message, *args)

    def info(self, message, *args):
        self._record('info', message, *args)

    def warn(self, message, *args):
        self._record('warn', message, *args)

    def error(self, message, *args):
        self._record('error', message, *args)

    def get_new_logger(self, name):
        return self
