# -*- coding: utf-8 -*-
"""
The entry points of the addon, the service and the context menu hook

Copyright (c) 2017-2018, Leo Moll
SPDX-License-Identifier: MIT
"""

# -- Imports ------------------------------------------------
# pylint: disable=import-error
import xbmcaddon

import resources.lib.appContext as appContext
from resources.lib.loggerKodi import LoggerKodi
from resources.lib.notifierKodi import NotifierKodi
from resources.lib.settingsKodi import SettingsKodi


# -- Functions ----------------------------------------------
def _init_app_context():
    """ Populates the global application context every entry point relies on """
    appContext.init()
    appContext.initAddon(xbmcaddon.Addon())
    appContext.initLogger(LoggerKodi(
        appContext.ADDONCLASS.getAddonInfo('id'),
        appContext.ADDONCLASS.getAddonInfo('version')))
    appContext.initSettings(SettingsKodi(appContext.ADDONCLASS))
    appContext.initNotifier(NotifierKodi(appContext.ADDONCLASS))


def run_plugin():
    """ Runs the plugin """
    # Imported here so that the service does not pay for the plugin's imports
    from resources.lib.plugin import MediathekViewPlugin
    _init_app_context()
    plugin = MediathekViewPlugin()
    plugin.run()
    plugin.exit()


def run_service():
    """ Runs the background service """
    from resources.lib.service import MediathekViewService
    _init_app_context()
    service = MediathekViewService()
    service.init()
    service.run()
    service.exit()


def run_context_menu(search):
    """ Opens the addon with the results for the given search term """
    from resources.lib.contextmenu import open_search
    open_search(search)
