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
        self.metadata = None
        self.showMetadata = None

    def generateItems(self, seasons, channel, show, showname='', pMetadata=None):
        """
        Returns one folder per season, ready to go into a film listing.

        The films themselves are listed by the film UI, so this hands back
        items rather than a directory of its own. `show` is the id the url
        needs, `showname` the name everything else is about.
        """
        self.metadata = pMetadata
        self.showMetadata = pMetadata.forShow(showname) if pMetadata else None
        items = []
        for (number, films) in seasons:
            targetUrl = self.plugin.build_url({
                'mode': 'films',
                'channel': channel if channel else '0',
                'show': show if show else '0',
                'season': number
            })
            items.append((targetUrl, self._generateListItem(number, films, showname), True))
        return items

    def _generateListItem(self, number, films, show):
        label = self.plugin.language(30992) % number
        if self.plugin.get_kodi_version() > 17:
            listitem = xbmcgui.ListItem(label=label, offscreen=True)
        else:
            listitem = xbmcgui.ListItem(label=label)
        info_labels = {
            'title': label,
            'sorttitle': label,
            'tvshowtitle': show,
            'season': number,
            'mediatype': 'season'
        }
        season = self.metadata.seasonOf(show, number) if self.metadata else None
        if self.showMetadata:
            # A season of its own is rarely described, so the show's
            # description stands in - it is about the same programme.
            plot = (season or {}).get('plot') or self.showMetadata.get('plot')
            if plot:
                info_labels['plot'] = plot
            for (field, key) in (('genre', 'genres'), ('mpaa', 'mpaa')):
                if self.showMetadata.get(key):
                    info_labels[field] = self.showMetadata[key]
        listitem.setInfo(type='video', infoLabels=info_labels)
        # The artwork of the channel the season was broadcast on, taken from
        # the films rather than from the listing: a show can run on more than
        # one channel.
        (icon, fanart) = artFor(self.plugin.path, films[0][CHANNEL] if films else '')
        # The season's own poster where there is one, the show's otherwise.
        poster = ((season or {}).get('poster')
                  or (self.showMetadata or {}).get('poster'))
        if self.showMetadata and self.showMetadata.get('fanart'):
            fanart = self.showMetadata['fanart']
        art = {'thumb': poster or icon, 'icon': icon, 'fanart': fanart}
        if poster:
            art['poster'] = poster
        listitem.setArt(art)
        return listitem
