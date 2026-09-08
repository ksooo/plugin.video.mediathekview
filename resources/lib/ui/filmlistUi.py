# -*- coding: utf-8 -*-
"""
The film model UI module

Copyright 2017-2019, Leo Moll and Dominik Schlösser
SPDX-License-Identifier: MIT
"""

import re
import time
import os
from datetime import datetime
# pylint: disable=import-error
import xbmcgui
import xbmcplugin
import resources.lib.appContext as appContext
from resources.lib.model.film import Film

# MediathekView leaves the season and episode inside the title, in the one
# shape it is consistent about: "(S01/E11)" or "(S2024E80)". 57150 of 715993
# films carry it. The other forms it uses - "Folge 6", "(1/4)", "Teil 2" -
# are fewer and ambiguous, "(1/4)" as often meaning part one of four, so they
# are left where they are.
EPISODE_MARKER = re.compile(r'\s*\(\s*S(\d{1,4})\s*/?\s*E(\d{1,4})\s*\)\s*', re.I)
# Kodi rebuilds the label of a plugin item from the label mask of the sort
# method in force - only an item that calls its label preformatted is left
# alone, and a plugin item does not. So this, rather than the label handed to
# the ListItem, is what the list actually shows, and it is built out of the
# fields rather than out of a composed string: %Z is the show, %H the season
# and episode as "1x11", %T the title. Each bracketed part disappears when
# its field is empty, so a film with neither show nor episode is its title.
LABEL_MASK_LONG = '[%Z: ][%H. ]%T'
LABEL_MASK_SHORT = '[%H. ]%T'
# The film list carries subtitles for German public service broadcasters, and
# says nothing about their language.
SUBTITLE_LANGUAGE = 'de'
# What Kodi is told about a stream the film list calls HD. The list itself
# gives no resolution; this is what those streams measure.
HD_STREAM = {'width': 1920, 'height': 1080}


def splitEpisode(title):
    """
    Takes the season and episode out of a title that carries them.

    Returns the title without the marker and the two numbers, or the title as
    it came and no numbers.
    """
    match = EPISODE_MARKER.search(title)
    if match is None:
        return (title, None, None)
    return (EPISODE_MARKER.sub(' ', title).strip(),
            int(match.group(1)), int(match.group(2)))


class FilmlistUi(object):
    """
    The filmui which generates a film list from data

    Args:
        plugin(MediathekView): the plugin object
    """

    def __init__(self, plugin, pLongTitle=True):
        self.logger = appContext.MVLOGGER.get_new_logger('FilmlistUI')
        self.plugin = plugin
        self.handle = plugin.addon_handle
        self.settings = appContext.MVSETTINGS
        self.useLongTitle = pLongTitle
        # define sortmethod for films
        # all av. sort method and put the default sortmethod on first place to be used by UI
        allSortMethods = [
            xbmcplugin.SORT_METHOD_UNSORTED,
            xbmcplugin.SORT_METHOD_TITLE,
            xbmcplugin.SORT_METHOD_DATE,
            xbmcplugin.SORT_METHOD_DATEADDED,
            xbmcplugin.SORT_METHOD_DURATION,
            # Only films whose title carried a marker have an episode number,
            # but for a series that is the order they belong in. It sits at
            # the end so that the settings keep addressing the same methods.
            xbmcplugin.SORT_METHOD_EPISODE
        ]
        method = allSortMethods[0]
        allSortMethods[0] = allSortMethods[self.settings.getFilmSortMethod()]
        allSortMethods[self.settings.getFilmSortMethod()] = method
        self.sortmethods = allSortMethods
        self.labelMask = LABEL_MASK_LONG if pLongTitle else LABEL_MASK_SHORT
        #
        self.startTime = 0

    def generate(self, databaseRs):
        #
        # 0 - idhash, 1 - title, 2 - showname, 3 - channel,
        # 4 - description, 5 - duration, 6 - aired,
        # 7- url_sub, 8- url_video, 9 - url_video_sd, 10 - url_video_hd
        #
        self.startTime = time.time()
        #
        xbmcplugin.setContent(self.handle, self.settings.getContentType())
        for method in self.sortmethods:
            xbmcplugin.addSortMethod(self.handle, method, self.labelMask)
        #
        aFilm = Film()
        listOfElements = []
        for element in databaseRs:
            #
            aFilm.init(element[0], element[1], element[2], element[3], element[4], element[5],
                        element[6], element[7], element[8], element[9], element[10])
            #
            (targetUrl, list_item) = self._generateListItem(aFilm)
            #
            if list_item is None:
                self.logger.warn('Skipping film without video url: {} - {}', aFilm.channel, aFilm.title)
                continue
            #
            list_item.addContextMenuItems(self._generateContextMenu(aFilm))
            #
            if self.settings.getAutoSub() and aFilm.url_sub:
                targetUrl = self.plugin.build_url({
                    'mode': "playwithsrt",
                    'id': aFilm.filmid
                })
            #
            listOfElements.append((targetUrl, list_item, False))
        #
        xbmcplugin.addDirectoryItems(
            handle=self.handle,
            items=listOfElements,
            totalItems=len(listOfElements)
        )
        #
        xbmcplugin.endOfDirectory(self.handle, cacheToDisc=False)
        self.plugin.setViewId(self.plugin.resolveViewId('LIST'))
        #
        self.logger.debug('generated: {} sec', time.time() - self.startTime)

    def _generateListItem(self, pFilm):
        #
        isHd = False
        if (pFilm.url_video_hd != "" and self.settings.getPreferHd()):
            videourl = pFilm.url_video_hd
            isHd = True
        elif (pFilm.url_video_sd != ""):
            videourl = pFilm.url_video_sd
        else:
            videourl = pFilm.url_video

        # exit if no url supplied. Both callers unpack the result, so the
        # failure has to keep the shape of the success.
        if videourl == "":
            return (None, None)

        videourl = videourl + self.settings.getUserAgentString()

        (filmtitle, season, episode) = splitEpisode(pFilm.title)

        if self.useLongTitle:
            resultingtitle = pFilm.show + ': ' + filmtitle
        else:
            resultingtitle = filmtitle

        # The label is what the list shows; the title is what everything else
        # reads, the player included. Putting the composed line in both left
        # the show name inside the film's own title.
        info_labels = {
            'title': filmtitle,
            'sorttitle': resultingtitle,
            'tvshowtitle': pFilm.show,
            # The channel is the broadcaster, and until now it reached the
            # screen only as an icon.
            'studio': pFilm.channel,
            'plot': pFilm.description
        }

        if season is not None:
            info_labels['season'] = season
            info_labels['episode'] = episode
            # Only where both were found: it is what makes a skin show them,
            # and calling everything else an episode would be a guess.
            info_labels['mediatype'] = 'episode'

        if pFilm.seconds is not None and pFilm.seconds > 0:
            info_labels['duration'] = pFilm.seconds

        if pFilm.aired is not None and pFilm.aired != 0:
            ndate = datetime.fromtimestamp(pFilm.aired)
            airedstring = ndate.isoformat().replace('T', ' ')
            info_labels['date'] = airedstring[:10]
            info_labels['aired'] = airedstring[:10]
            info_labels['dateadded'] = airedstring

        icon = os.path.join(
            self.plugin.path,
            'resources',
            'icons',
            'sender',
            pFilm.channel.lower() + '-i.png'
        )
        fanart = os.path.join(
            self.plugin.path,
            'resources',
            'icons',
            'sender',
            pFilm.channel.lower() + '-f.png'
        )

        #
        if self.plugin.get_kodi_version() > 17:
            listitem = xbmcgui.ListItem(label=resultingtitle, path=videourl, offscreen=True)
        else:
            listitem = xbmcgui.ListItem(label=resultingtitle, path=videourl)
        #
        listitem.setInfo(type='video', infoLabels=info_labels)
        listitem.setProperty('IsPlayable', 'true')
        # That a subtitle exists was only findable in the context menu. As a
        # stream it becomes something a skin can put a flag on, and it is one
        # of the few things the film list tells us for certain.
        if pFilm.url_sub:
            listitem.addStreamInfo('subtitle', {'language': SUBTITLE_LANGUAGE})
        if isHd:
            # " (HD)" used to be appended to the title. Nothing is claimed for
            # the other streams: the film list does not say what they are.
            listitem.addStreamInfo('video', dict(HD_STREAM))
        listitem.setArt({
            'thumb': icon,
            'icon': icon,
            'fanart': fanart
        })
        return (videourl, listitem)

    def _generateContextMenu(self, pFilm):
        contextmenu = []

        if pFilm.url_sub != '':
            contextmenu.append((
                self.plugin.language(30921),
                'PlayMedia({})'.format(
                    self.plugin.build_url({
                        'mode': "playwithsrt",
                        'id': pFilm.filmid
                    })
                )
            ))

        # Download movie
        contextmenu.append((
            self.plugin.language(30922),
            'RunPlugin({})'.format(
                self.plugin.build_url({
                    'mode': "downloadmv",
                    'id': pFilm.filmid
                })
            )
        ))
        # Download TV episode
        contextmenu.append((
            self.plugin.language(30924),
            'RunPlugin({})'.format(
                self.plugin.build_url({
                    'mode': "downloadep",
                    'id': pFilm.filmid
                })
            )
        ))
        return contextmenu

