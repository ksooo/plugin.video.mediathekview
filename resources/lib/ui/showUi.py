# -*- coding: utf-8 -*-
"""
The show model UI module

Copyright 2017-2018, Leo Moll and Dominik Schlösser
SPDX-License-Identifier: MIT
"""

# pylint: disable=import-error
import time
import resources.lib.appContext as appContext
from resources.lib.ui.channelArt import artFor
import os
import xbmcgui
import xbmcplugin

import resources.lib.mvutils as mvutils
from resources.lib.model.show import Show


class ShowUi(object):
    """
    The show model view class

    Args:
        plugin(MediathekView): the plugin object
    """

    def __init__(self, plugin):
        self.logger = appContext.MVLOGGER.get_new_logger('ShowUI')
        self.plugin = plugin
        self.handle = plugin.addon_handle
        self.startTime = 0

    def generate(self, databaseRs, pMetadata=None):
        #
        # 0 - showid
        # 1 - channelId
        # 2 - showname
        # 3 - channel
        #
        self.startTime = time.time()
        #
        xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_TITLE)
        xbmcplugin.setContent(self.handle, '')
        #
        showModel = Show()
        listOfElements = []
        # Read only: a channel can hold 1746 shows, so nothing here asks the
        # service. What was looked up when a show was opened turns up here.
        for element in databaseRs:
            #
            showModel.init(element[0], element[1], element[2], element[3])
            #
            if element[1].find(',') == -1:
                nameLabel = element[2];
                (icon, fanart) = artFor(self.plugin.path, element[1])
            else:
                nameLabel = element[2] + ' [' + element[3] + ']';
                icon = os.path.join(
                    self.plugin.path,
                    'resources',
                    'icons',
                    'default2-m.png'
                )
                fanart = os.path.join(
                    self.plugin.path,
                    'resources',
                    'icons',
                    'default2-f.png'
                )
            #
            if self.plugin.get_kodi_version() > 17:
                list_item = xbmcgui.ListItem(label=nameLabel, offscreen=True)
            else:
                list_item = xbmcgui.ListItem(label=nameLabel)
            #

            info_labels = {
                'title': nameLabel,
                'sorttitle': nameLabel.lower(),
                'tvshowtitle': element[2],
                'mediatype': 'tvshow'
            }
            record = pMetadata.forShow(element[2]) if pMetadata else None
            poster = None
            if record:
                for (field, key) in (('plot', 'plot'), ('genre', 'genres'),
                                     ('premiered', 'premiered'), ('mpaa', 'mpaa')):
                    if record.get(key):
                        info_labels[field] = record[key]
                if record.get('rating'):
                    info_labels['rating'] = record['rating']
                    info_labels['votes'] = record.get('votes') or 0
                poster = record.get('poster')
                fanart = record.get('fanart') or fanart

            art = {'thumb': poster or icon, 'icon': icon, 'fanart': fanart}
            if poster:
                art['poster'] = poster
            list_item.setArt(art)
            list_item.setInfo(type='video', infoLabels=info_labels)
            if record and record.get('imdbid'):
                list_item.setUniqueIDs({'imdb': record['imdbid']}, 'imdb')
            #
            targetUrl = mvutils.build_url({
                'mode': 'films',
                'channel' : element[1].replace(',', '|'),
                'show': element[0]
            })
            #
            contextmenu = []
            contextmenu.append((
            self.plugin.language(30922),
            'RunPlugin({})'.format(
                self.plugin.build_url({
                    'mode': "downloadmv",
                    'channel' : element[1].replace(',', '|'),
                    'show': element[0]
                })
            )
            ))
            # Download TV episode
            contextmenu.append((
                self.plugin.language(30924),
                'RunPlugin({})'.format(
                    self.plugin.build_url({
                        'mode': "downloadep",
                        'channel' : element[1].replace(',', '|'),
                        'show': element[0]
                    })
                )
            ))
            if pMetadata is not None and pMetadata.enabled():
                # The show is where a wrong poster is seen, so this is where
                # asking again belongs. Behind what the menu is mostly used
                # for, which is downloading.
                contextmenu.append((
                    self.plugin.language(30995),
                    'RunPlugin({})'.format(
                        self.plugin.build_url({
                            'mode': "refreshmetadata",
                            'showname': element[2]
                        })
                    )
                ))
            #
            list_item.addContextMenuItems(contextmenu)
            #
            listOfElements.append((targetUrl, list_item, True))
        #
        xbmcplugin.addDirectoryItems(
            handle=self.handle,
            items=listOfElements,
            totalItems=len(listOfElements)
        )
        #
        xbmcplugin.endOfDirectory(self.handle, cacheToDisc=False)
        #
        self.logger.debug('generated: {} sec', time.time() - self.startTime)
