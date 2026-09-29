# -*- coding: utf-8 -*-
"""
Opening a listing and putting the cursor on one of its films

SPDX-License-Identifier: MIT
"""

# -- Imports ------------------------------------------------
import time

# pylint: disable=import-error
import xbmc
import xbmcgui

import resources.lib.appContext as appContext

# -- Constants ----------------------------------------------
# How long a listing may take to appear before the jump gives up. Opening a
# show of 1700 films took under a second when measured; this is for a slow
# machine, not for a listing that never comes.
WAIT_SECONDS = 10
POLL_SECONDS = 0.1
RETRY_SECONDS = 1.0
# How long a listing that was asked for may stay away before it is asked for
# again. Kodi sets the path of a listing when it opens the window and fetches
# the items afterwards, so a listing asked for while another one is still
# being fetched is lost when that one arrives - which is what happens on a
# machine where the plugin takes its time.
# The window the listing appears in.
VIDEO_WINDOW = 10025


# -- Classes ------------------------------------------------
class Container(object):
    """ The few things Kodi is asked about the listing on screen """

    def activate(self, url):
        xbmc.executebuiltin('ActivateWindow(Videos,%s,return)' % url)

    def path(self):
        return xbmc.getInfoLabel('Container.FolderPath')

    def loading(self):
        return xbmc.getCondVisibility('Window.IsActive(busydialognocancel)')

    def viewId(self):
        """ The control the listing is drawn in, which is the focused one """
        return xbmcgui.Window(VIDEO_WINDOW).getFocusId()

    def count(self, viewId):
        return int(xbmc.getInfoLabel('Container(%d).NumAllItems' % viewId) or 0)

    def filmId(self, viewId, index):
        """
        The film at that position, counted as the screen shows it.

        ListItemAbsolute, because Kodi sorts the listing itself and
        ListItem(n) counts from whatever is selected.
        """
        return xbmc.getInfoLabel(
            'Container(%d).ListItemAbsolute(%d).Property(filmid)' % (viewId, index))

    def select(self, viewId, index):
        xbmc.executebuiltin('Control.SetFocus(%d,%d,absolute)' % (viewId, index))

    def waited(self, seconds):
        """ Returns whether Kodi wants to stop """
        return appContext.MVMONITOR.wait_for_abort(seconds)


class Jump(object):
    """
    Opens a listing and selects a film in it.

    Kodi offers no way to ask for a listing with an item preselected, so
    this opens the listing and waits for it: the plugin that fills it is a
    script of its own, and only once it has run does the item exist to be
    selected.
    """

    def __init__(self, container=None):
        self.logger = appContext.MVLOGGER.get_new_logger('Jump')
        self.container = container if container is not None else Container()

    def toFilm(self, url, filmId):
        """ Opens the listing that holds the film and puts the cursor on it """
        return self._select(url, filmId, time.time() + WAIT_SECONDS)

    def _opened(self, url, deadline):
        """ Waits for that listing, asking again while it does not come """
        asked = 0.0
        while time.time() < deadline:
            if self.container.path() == url and not self.container.loading():
                return True
            if time.time() - asked >= RETRY_SECONDS:
                self.container.activate(url)
                asked = time.time()
            if self.container.waited(POLL_SECONDS):
                return False
        self.logger.warn('Listing {} did not appear', url)
        return False

    def _select(self, url, filmId, deadline):
        """
        Puts the cursor on the film once the listing holds it.

        The path of a listing is Kodi's before its items are, so a listing
        that does not hold the film yet is one to look at again rather than
        one without it.
        """
        scanned = None
        looked = 0.0
        while time.time() < deadline:
            if not self._opened(url, deadline):
                return False
            viewId = self.container.viewId()
            count = self.container.count(viewId)
            if count != scanned or time.time() - looked >= RETRY_SECONDS:
                (scanned, looked) = (count, time.time())
                index = self._indexOf(viewId, filmId)
                if index is not None:
                    self.container.select(viewId, index)
                    return True
            if self.container.waited(POLL_SECONDS):
                return False
        # A filter can hide the film: the cursor then stays where Kodi put it.
        self.logger.debug('Film {} is not in {}', filmId, url)
        return False

    def _indexOf(self, viewId, filmId):
        for index in range(self.container.count(viewId)):
            if self.container.filmId(viewId, index) == filmId:
                return index
        return None
