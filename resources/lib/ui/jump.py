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

    def toFilm(self, urls, filmId):
        """
        Opens the listings in turn and puts the cursor on the film.

        More than one where the film sits behind a season: Kodi's ".." walks
        the listings that were shown, not the path, so the show has to be
        opened on the way for ".." to lead to its seasons.
        """
        for url in urls[:-1]:
            self.container.activate(url)
            if not self._appeared(url):
                return False
        url = urls[-1]
        self.container.activate(url)
        if not self._appeared(url):
            return False
        viewId = self.container.viewId()
        index = self._indexOf(viewId, filmId)
        if index is None:
            # The listing is the right one and the film is not in it, which
            # a filter can do: leave the cursor where Kodi put it.
            self.logger.debug('Film {} is not in {}', filmId, url)
            return False
        self.container.select(viewId, index)
        return True

    def _appeared(self, url):
        """ Waits until that listing is the one on screen """
        deadline = time.time() + WAIT_SECONDS
        while time.time() < deadline:
            if self.container.waited(POLL_SECONDS):
                return False
            if self.container.path() == url and not self.container.loading():
                return True
        self.logger.warn('Listing {} did not appear', url)
        return False

    def _indexOf(self, viewId, filmId):
        for index in range(self.container.count(viewId)):
            if self.container.filmId(viewId, index) == filmId:
                return index
        return None
