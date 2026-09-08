# -*- coding: utf-8 -*-
"""
The season UI module

SPDX-License-Identifier: MIT
"""

# pylint: disable=import-error
import xbmcgui
import resources.lib.appContext as appContext
from resources.lib.ui.channelArt import artFor

# Where the channel sits in a row of the film query.
CHANNEL = 3


class SeasonUi(object):
    """
    Builds the season folders that stand in front of a show's films

    Args:
        plugin(MediathekView): the plugin object
    """

    def __init__(self, plugin):
        self.logger = appContext.MVLOGGER.get_new_logger('SeasonUi')
        self.plugin = plugin

    def generateItems(self, seasons, channel, show):
        """
        Returns one folder per season, ready to go into a film listing.

        The films themselves are listed by the film UI, so this hands back
        items rather than a directory of its own.
        """
        items = []
        for (number, films) in seasons:
            targetUrl = self.plugin.build_url({
                'mode': 'films',
                'channel': channel if channel else '0',
                'show': show if show else '0',
                'season': number
            })
            items.append((targetUrl, self._generateListItem(number, films, show), True))
        return items

    def _generateListItem(self, number, films, show):
        label = self.plugin.language(30992) % number
        if self.plugin.get_kodi_version() > 17:
            listitem = xbmcgui.ListItem(label=label, offscreen=True)
        else:
            listitem = xbmcgui.ListItem(label=label)
        listitem.setInfo(type='video', infoLabels={
            'title': label,
            'sorttitle': label,
            'tvshowtitle': show,
            'season': number,
            'mediatype': 'season'
        })
        # The artwork of the channel the season was broadcast on, taken from
        # the films rather than from the listing: a show can run on more than
        # one channel.
        (icon, fanart) = artFor(self.plugin.path, films[0][CHANNEL] if films else '')
        listitem.setArt({
            'thumb': icon,
            'icon': icon,
            'fanart': fanart
        })
        return listitem
