# -*- coding: utf-8 -*-
"""
Fixtures for testing the addon outside Kodi

SPDX-License-Identifier: MIT
"""

import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ADDON_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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


class Notifier(object):
    """Records what would have been put on screen."""

    def __init__(self):
        self.errors = []
        self.notifications = []
        self.limit_results = []

    def show_error(self, heading, message):
        self.errors.append((heading, message))

    def show_database_error(self, err):
        self.errors.append(('database', err))

    def show_notification(self, heading, message):
        self.notifications.append((heading, message))

    def show_limit_results(self, maxresults):
        self.limit_results.append(maxresults)


class Settings(object):
    """The addon settings with usable defaults.

    Every getter the code under test needs is here; pass overrides as keyword
    arguments to change one for a single test.
    """

    _DEFAULTS = {
        'datapath': '',
        'preferHd': False,
        'autoSub': False,
        'noFutur': False,
        'minLength': 0,
        'maxResults': 1000,
        'maxAge': 2 * 86400,
        'recentMode': 0,
        'filmSortMethod': 0,
        'contentType': '',
        'groupShow': True,
        'caching': True,
        'userAgentString': '',
        'blacklist': '',
        'lastUpdate': 0,
        'lastFullUpdate': 0,
        'databaseStatus': 'IDLE',
        'databaseVersion': 3,
        'databaseType': 0,
    }

    def __init__(self, **overrides):
        self._values = dict(self._DEFAULTS)
        unknown = set(overrides) - set(self._DEFAULTS)
        if unknown:
            raise AssertionError('unknown setting(s): %s' % ', '.join(sorted(unknown)))
        self._values.update(overrides)

    def getDatapath(self):
        return self._values['datapath']

    def getPreferHd(self):
        return self._values['preferHd']

    def getAutoSub(self):
        return self._values['autoSub']

    def getNoFutur(self):
        return self._values['noFutur']

    def getMinLength(self):
        return self._values['minLength']

    def getMaxResults(self):
        return self._values['maxResults']

    def getMaxAge(self):
        return self._values['maxAge']

    def getRecentMode(self):
        return self._values['recentMode']

    def getFilmSortMethod(self):
        return self._values['filmSortMethod']

    def getContentType(self):
        return self._values['contentType']

    def getGroupShow(self):
        return self._values['groupShow']

    def getCaching(self):
        return self._values['caching']

    def getUserAgentString(self):
        return self._values['userAgentString']

    def getBlacklist(self):
        return self._values['blacklist']

    def getLastUpdate(self):
        return self._values['lastUpdate']

    def setLastUpdate(self, value):
        self._values['lastUpdate'] = value

    def getLastFullUpdate(self):
        return self._values['lastFullUpdate']

    def setLastFullUpdate(self, value):
        self._values['lastFullUpdate'] = value

    def getDatabaseStatus(self):
        return self._values['databaseStatus']

    def setDatabaseStatus(self, value):
        self._values['databaseStatus'] = value

    def getDatabaseVersion(self):
        return self._values['databaseVersion']

    def setDatabaseVersion(self, value):
        self._values['databaseVersion'] = value

    def getDatabaseType(self):
        return self._values['databaseType']


class Addon(object):
    """Stands in for xbmcaddon.Addon."""

    def __init__(self, strings=None, info=None):
        self.strings = strings if strings is not None else {}
        self.info = info if info is not None else {
            'id': 'plugin.video.mediathekview.ksooo',
            'name': 'MediathekView (ksooo)',
            'version': '1.0.0',
            'path': ADDON_PATH,
            'profile': ADDON_PATH,
        }
        self.settings = {}

    def getLocalizedString(self, string_id):
        return self.strings.get(string_id, '')

    def getAddonInfo(self, key):
        return self.info.get(key, '')

    def getSetting(self, key):
        return self.settings.get(key, '')

    def setSetting(self, key, value):
        self.settings[key] = value


class Cursor(object):

    def __init__(self, connection):
        self._connection = connection
        self._rows = []
        self.rowcount = 0

    def execute(self, statement, params=None):
        self._connection.executed.append((statement, params))
        if self._connection.error is not None:
            raise self._connection.error
        self._rows = self._connection.next_result()
        self.rowcount = len(self._rows)

    def executemany(self, statement, params):
        self._connection.executed.append((statement, params))
        if self._connection.error is not None:
            raise self._connection.error
        self.rowcount = len(list(params))

    def fetchall(self):
        return self._rows

    def close(self):
        pass


class Connection(object):
    """A database connection that records statements instead of running them.

    ``results`` is handed out one entry per execute, so a test can line up the
    answers a method expects. ``error`` makes every execute raise.
    """

    def __init__(self, results=None, error=None):
        self.executed = []
        self.results = list(results) if results else []
        self.error = error
        self.commits = 0

    def next_result(self):
        return self.results.pop(0) if self.results else []

    def cursor(self):
        return Cursor(self)

    def commit(self):
        self.commits += 1

    @property
    def statements(self):
        return [statement for (statement, _) in self.executed]


class Plugin(object):
    """Stands in for MediathekViewPlugin where a UI class needs one."""

    def __init__(self, strings=None, database=None):
        self.addon_handle = 1
        self.path = ADDON_PATH
        self.strings = strings if strings is not None else {}
        self.database = database
        self.view_ids = []

    def language(self, string_id):
        return self.strings.get(string_id, '')

    def build_url(self, params):
        return 'plugin://test/?' + '&'.join(
            '%s=%s' % (key, value) for key, value in sorted(params.items()))

    def get_kodi_version(self):
        return 21

    def resolveViewId(self, name):
        return -1

    def setViewId(self, view_id):
        self.view_ids.append(view_id)


class ListItem(object):
    """Records what the addon puts on a Kodi list item."""

    def __init__(self, label='', label2='', path='', offscreen=False):
        self.label = label
        self.path = path
        self.info = {}
        self.art = {}
        self.properties = {}
        self.context_menu = []
        self.subtitles = []

    def setInfo(self, type, infoLabels):
        self.info = infoLabels

    def setArt(self, art):
        self.art = art

    def setProperty(self, key, value):
        self.properties[key] = value

    def addContextMenuItems(self, items):
        self.context_menu.extend(items)

    def setSubtitles(self, subtitles):
        self.subtitles = subtitles


class _Dialog(object):
    """The xbmcgui.Dialog stub: records instead of showing."""

    calls = []

    def notification(self, heading, message, icon=None, time=0, sound=True):
        _Dialog.calls.append(('notification', heading, message))

    def ok(self, heading, message):
        _Dialog.calls.append(('ok', heading, message))

    def textviewer(self, heading, text):
        _Dialog.calls.append(('textviewer', heading, text))


class _DialogProgressBG(object):
    """The xbmcgui.DialogProgressBG stub: accepts and forgets."""

    def create(self, heading, message=''):
        pass

    def update(self, percent=0, heading=None, message=None):
        pass

    def close(self):
        pass


class _Plugin(object):
    """The xbmcplugin stub: records the directory the addon builds."""

    SORT_METHOD_UNSORTED = 0
    SORT_METHOD_TITLE = 1
    SORT_METHOD_DATE = 2
    SORT_METHOD_DATEADDED = 3
    SORT_METHOD_DURATION = 4

    def __init__(self):
        self.items = []
        self.content = None
        self.sort_methods = []
        self.ended = False

    def reset(self):
        self.__init__()

    def setContent(self, handle, content):
        self.content = content

    def addSortMethod(self, handle, method):
        self.sort_methods.append(method)

    def addDirectoryItems(self, handle, items, totalItems=0):
        self.items.extend(items)

    def addDirectoryItem(self, handle, url, listitem, isFolder=False):
        self.items.append((url, listitem, isFolder))

    def endOfDirectory(self, handle, succeeded=True, updateListing=False,
                       cacheToDisc=False):
        self.ended = True

    def setResolvedUrl(self, handle, succeeded, listitem):
        self.items.append((None, listitem, False))


def install_kodi_stubs():
    """Registers stand-ins for the Kodi modules and returns the xbmcplugin one.

    Deliberately not done on import: mvutils decides on ``import xbmcvfs``
    whether it is running inside Kodi, so a stub that is always present would
    silently send it down the Kodi path in every test. Only tests that need
    the stubs ask for them.
    """
    xbmc = sys.modules.setdefault('xbmc', types.ModuleType('xbmc'))
    xbmc.LOGDEBUG = 0
    xbmc.LOGINFO = 1
    xbmc.LOGWARNING = 2
    xbmc.LOGERROR = 3
    xbmc.LOGFATAL = 4
    xbmc.log = lambda *args, **kwargs: None
    xbmc.getInfoLabel = lambda label: '21.0'
    xbmc.executebuiltin = lambda command: None

    gui = sys.modules.setdefault('xbmcgui', types.ModuleType('xbmcgui'))
    gui.ListItem = ListItem
    gui.NOTIFICATION_INFO = 'info'
    gui.NOTIFICATION_WARNING = 'warning'
    gui.NOTIFICATION_ERROR = 'error'
    gui.Dialog = _Dialog
    gui.DialogProgressBG = _DialogProgressBG

    sys.modules.setdefault('xbmcaddon', types.ModuleType('xbmcaddon'))
    sys.modules.setdefault('xbmcvfs', types.ModuleType('xbmcvfs'))

    existing = sys.modules.get('xbmcplugin')
    if isinstance(existing, _Plugin):
        existing.reset()
        return existing
    plugin = _Plugin()
    sys.modules['xbmcplugin'] = plugin
    return plugin


def _no_connection(**kwargs):
    return None


def install_mysql_stub(connect=_no_connection):
    """Registers a mysql.connector whose connect() is the given callable.

    The addon imports it at module level, and the real package is not a
    dependency of the tests, so anything reaching storeMySql - the updater and
    the plugin both do - needs it present. init_app_context() installs one that
    connects to nothing, which is why no test module has to remember to; call
    this afterwards to put a recording one in its place.
    """
    package = sys.modules.setdefault('mysql', types.ModuleType('mysql'))
    connector = types.ModuleType('mysql.connector')
    connector.__version__ = '8.0.33'
    connector.__version_info__ = (8, 0, 33)
    connector.HAVE_CEXT = False
    connector.connect = connect
    sys.modules['mysql.connector'] = connector
    package.connector = connector
    return connector


def init_app_context(settings=None, notifier=None):
    """Fills the global application context the addon modules read from."""
    install_kodi_stubs()
    install_mysql_stub()
    import resources.lib.appContext as app_context
    app_context.init()
    app_context.initLogger(Logger())
    app_context.initSettings(settings if settings is not None else Settings())
    app_context.initNotifier(notifier if notifier is not None else Notifier())
    return app_context
