# -*- coding: utf-8 -*-
"""
The context menu hook

Copyright (c) 2017-2018, codingPF
SPDX-License-Identifier: MIT
"""

# -- Imports ------------------------------------------------
# pylint: disable=import-error
import xbmc


try:
    # Python 3.x
    from urllib.parse import urlencode
except ImportError:
    # Python 2.x
    from urllib import urlencode


# -- Functions ----------------------------------------------
def open_search(search):
    """ Opens the addon showing the results for the given search term """
    params = {'mode': 'research', 'doNotSave': 'true', 'search': search}
    cmd = 'ActivateWindow(Videos,plugin://plugin.video.mediathekview.ksooo?' + \
        urlencode(params) + ')'
    xbmc.executebuiltin(cmd)
