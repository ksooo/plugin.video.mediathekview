# -*- coding: utf-8 -*-
"""
The film model UI module

Copyright 2017-2019, Leo Moll and Dominik Schlösser
SPDX-License-Identifier: MIT
"""

import time
import os
from datetime import datetime
# pylint: disable=import-error
import xbmc
import xbmcgui
import xbmcplugin
import resources.lib.appContext as appContext
import resources.lib.ui.videoInfo as videoInfo
from resources.lib.ui.channelArt import artFor
from resources.lib.model.film import Film
from resources.lib.seasons import splitEpisode

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
# What a broadcast time looks like where Kodi's region settings say nothing.
DATE_FORMAT = '%d.%m.%Y'
TIME_FORMAT = '%H:%M'
# What Kodi is told about a stream the film list calls HD. The list itself
# gives no resolution; this is what those streams measure.
HD_STREAM = {'width': 1920, 'height': 1080}
# Where the show's id sits in a row of the film query. A jump to the show
# needs it; nothing else on the item does.
SHOWID = 11
# What the listing holds, which is what decides how a skin lays out its
# rows: with a content type Kodi and Estuary show the watched state and no
# artwork in the row and put the picture of an episode beside the list;
# with none, every row carries a picture of its own.
CONTENT_TYPE = 'episodes'


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
        if not pLongTitle:
            # This is the listing of a single show, and a show is watched in
            # its own order. Where no episode numbers were found they are all
            # zero, and the list stays as the query delivered it.
            allSortMethods.remove(xbmcplugin.SORT_METHOD_EPISODE)
            allSortMethods.insert(0, xbmcplugin.SORT_METHOD_EPISODE)
        self.sortmethods = allSortMethods
        self.labelMask = LABEL_MASK_LONG if pLongTitle else LABEL_MASK_SHORT
        # What an external service knows about the shows of this listing, by
        # name. Nothing here asks; the caller brings what is stored.
        self.showMetadata = {}
        # The picture of each episode on screen, by show, season and
        # episode number, where the service had any.
        self.stills = {}
        # The poster of each season on screen, by show and season.
        self.seasonPosters = {}
        # The entry that refreshes metadata is only offered where metadata
        # is shown: with the feature on, in the listing of a single show.
        self.metadataEnabled = self.settings.getTmdbEnabled() and not pLongTitle
        #
        self.startTime = 0

    def generate(self, databaseRs, pLeadingItems=None, pShowMetadata=None, pStills=None,
                 pSeasonPosters=None):
        #
        # 0 - idhash, 1 - title, 2 - showname, 3 - channel,
        # 4 - description, 5 - duration, 6 - aired,
        # 7- url_sub, 8- url_video, 9 - url_video_sd, 10 - url_video_hd
        #
        self.startTime = time.time()
        self.showMetadata = pShowMetadata or {}
        self.stills = pStills or {}
        self.seasonPosters = pSeasonPosters or {}
        #
        xbmcplugin.setContent(self.handle, CONTENT_TYPE)
        for method in self.sortmethods:
            xbmcplugin.addSortMethod(self.handle, method, self.labelMask)
        #
        aFilm = Film()
        # Seasons, where the show has any, share the listing with the films
        # that name none. Kodi puts folders first by itself.
        listOfElements = list(pLeadingItems) if pLeadingItems else []
        for element in databaseRs:
            #
            aFilm.init(element[0], element[1], element[2], element[3], element[4], element[5],
                        element[6], element[7], element[8], element[9], element[10])
            #
            (targetUrl, list_item) = self._generateListItem(
                aFilm, element[SHOWID] if len(element) > SHOWID else '')
            #
            if list_item is None:
                self.logger.warn('Skipping film without video url: {} - {}', aFilm.channel, aFilm.title)
                continue
            #
            list_item.addContextMenuItems(self._generateContextMenu(
                aFilm, element[SHOWID] if len(element) > SHOWID else ''))
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
        #
        self.logger.debug('generated: {} sec', time.time() - self.startTime)

    def _generateListItem(self, pFilm, pShowId=''):
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

        record = self.showMetadata.get(pFilm.show)
        if record:
            # The show's, not the film's: a genre and an age rating belong to
            # the programme. Its plot, rating and first broadcast do not - the
            # film has its own description and its own airdate.
            for (field, key) in (('genre', 'genres'), ('mpaa', 'mpaa')):
                if record.get(key):
                    info_labels[field] = record[key]

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
            info_labels['date'] = ndate.isoformat()
            info_labels['aired'] = airedstring[:10]
            info_labels['dateadded'] = airedstring
            # In front of the description, because that is the only text of
            # ours a skin shows beside a listing. Kodi's own fields carry the
            # broadcast as a date and drop the time of day.
            info_labels['plot'] = _broadcast(
                self.plugin.language(30136), ndate, pFilm.description)

        (icon, fanart) = artFor(self.plugin.path, pFilm.channel)
        still = (self.stills.get((pFilm.show, season, episode))
                 if season is not None else None)
        poster = (record or {}).get('poster')
        if record:
            fanart = record.get('fanart') or fanart

        #
        listitem = xbmcgui.ListItem(label=resultingtitle, path=videourl, offscreen=True)
        #
        videoInfo.apply(listitem, info_labels)
        listitem.setProperty('IsPlayable', 'true')
        # What a jump to this film looks for once the listing is on screen.
        listitem.setProperty('filmid', pFilm.filmid)
        # That a subtitle exists was only findable in the context menu. As a
        # stream it becomes something a skin can put a flag on, and it is one
        # of the few things the film list tells us for certain.
        if pFilm.url_sub:
            listitem.getVideoInfoTag().addSubtitleStream(
                xbmc.SubtitleStreamDetail(SUBTITLE_LANGUAGE))
        if isHd:
            # " (HD)" used to be appended to the title. Nothing is claimed for
            # the other streams: the film list does not say what they are.
            listitem.getVideoInfoTag().addVideoStream(
                xbmc.VideoStreamDetail(**HD_STREAM))
        # A film wears its own picture and nothing else, which is how a
        # library episode is furnished too: the channel logo where the
        # service had none, and no poster of the show. A skin shows the
        # picture of an episode beside the list rather than in the row, and
        # it takes the poster in preference to it wherever one is set -
        # Estuary in ShiftThumbVar - so the show's poster would push the
        # episode's own picture off the screen. It stays on the show and on
        # the season, where it belongs.
        art = {'thumb': still or icon, 'icon': icon, 'fanart': fanart}
        # Under their own keys, not as `poster`, which a skin would show
        # instead of the episode's own picture. This is where Kodi keeps the
        # posters of a library episode and where the information dialog
        # looks for them: it shows the season's poster, or the show's, with
        # the episode's picture in front of it.
        if poster:
            art['tvshow.poster'] = poster
        seasonPoster = self.seasonPosters.get((pFilm.show, season))
        if seasonPoster:
            art['season.poster'] = seasonPoster
        listitem.setArt(art)
        return (videourl, listitem)

    def _generateContextMenu(self, pFilm, pShowId=''):
        contextmenu = []

        (_, season, _) = splitEpisode(pFilm.title)
        if self.useLongTitle and season is not None and pShowId:
            # Only where the listing spans shows, and only for a film that
            # names an episode: in the listing of a show the entry would
            # lead where the user already is, and a film that is no episode
            # has no place of its own to be shown in.
            contextmenu.append((
                self.plugin.language(30132),
                'RunPlugin({})'.format(
                    self.plugin.build_url({
                        'mode': "gotoshow",
                        'channel': pFilm.channel,
                        'show': pShowId,
                        'id': pFilm.filmid
                    })
                )
            ))

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
        if self.metadataEnabled:
            # Behind what the menu is mostly used for, which is downloading.
            contextmenu.append((
                self.plugin.language(30995),
                'RunPlugin({})'.format(
                    self.plugin.build_url({
                        'mode': "refreshmetadata",
                        'showname': pFilm.show
                    })
                )
            ))
        return contextmenu


def _broadcast(label, when, description):
    """ The description with the broadcast time in front of it """
    shown = label.format(when.strftime('%s %s' % (_region('dateshort', DATE_FORMAT),
                                                  _region('time', TIME_FORMAT))))
    return '%s\n\n%s' % (shown, description) if description else shown


def _region(name, fallback):
    """
    How Kodi's settings say to write a date or a time, or ours.

    The seconds go: a broadcast is announced to the minute, and Kodi's own
    time format carries them.
    """
    fmt = xbmc.getRegion(name) or fallback
    return fmt.replace(':%S', '').replace('%S', '').strip()
