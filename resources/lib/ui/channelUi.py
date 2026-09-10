# -*- coding: utf-8 -*-
"""
The channel model UI module

Copyright 2017-2018, Leo Moll and Dominik Schlösser
SPDX-License-Identifier: MIT
"""

# pylint: disable=import-error
import time
import resources.lib.appContext as appContext
import resources.lib.ui.videoInfo as videoInfo
from resources.lib.ui.channelArt import artFor
import os
import xbmcgui
import xbmcplugin
import resources.lib.mvutils as mvutils

from resources.lib.model.channel import Channel


class ChannelUi(object):
    """
    The channel model view class

    Args:
        plugin(MediathekView): the plugin object

    """

    def __init__(self, plugin, targetUrl):
        self.logger = appContext.MVLOGGER.get_new_logger('ChannelUi')
        self.plugin = plugin
        self.handle = plugin.addon_handle
        self.targetUrl = targetUrl
        self.startTime = 0

    def generate(self, databaseRs):
        #
        # 0 - channelid
        # 1 - channel
        # 2 - channel description xxx (#no)
        #
        #
        self.startTime = time.time()
        #
        xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_TITLE)
        xbmcplugin.setContent(self.handle, '')
        #
        channelModel = Channel()
        listOfElements = []
        for element in databaseRs:
            #
            channelModel.init(element[0], element[1], element[2])
            #
            labelname = channelModel.channelCaption
            if channelModel.count > 0:
                labelname += ' (' + str(channelModel.count) + ')'
            #
            list_item = xbmcgui.ListItem(label=labelname, offscreen=True)
            #
            (icon, fanart) = artFor(self.plugin.path, channelModel.channelId)
            list_item.setArt({
                'thumb': icon,
                'icon': icon,
                'fanart': fanart
            })

            info_labels = {
                'title': labelname,
                'sorttitle': channelModel.channelCaption.lower()
            }
            videoInfo.apply(list_item, info_labels)
            #
            targetUrl = mvutils.build_url({
                'mode': self.targetUrl,
                'channel': channelModel.channelId
            })
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

