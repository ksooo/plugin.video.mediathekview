# -*- coding: utf-8 -*-
"""
Tests for the film list UI

SPDX-License-Identifier: MIT
"""

import calendar
import contextlib
import os
import time
import unittest

from tests import support

support.init_app_context()

from resources.lib.ui.filmlistUi import FilmlistUi


def row(idhash='hash', title='Titel', show='Sendung', channel='ARD',
        description='', seconds=60, aired=0, url_sub='',
        url_video='https://example.org/a.mp4', url_video_sd='', url_video_hd=''):
    return (idhash, title, show, channel, description, seconds, aired,
            url_sub, url_video, url_video_sd, url_video_hd)


class GenerateTest(unittest.TestCase):

    def setUp(self):
        self.xbmcplugin = support.install_kodi_stubs()
        self.plugin = support.Plugin()

    def _generate(self, rows):
        FilmlistUi(self.plugin).generate(rows)
        return self.xbmcplugin.items

    def test_lists_a_film(self):
        items = self._generate([row(title='Tagesschau')])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0][1].label, 'Sendung: Tagesschau')

    def test_a_film_without_any_url_does_not_take_the_list_with_it(self):
        # A record whose Url field is empty reaches the database unfiltered.
        # It used to make _generateListItem return a bare None, and unpacking
        # that raised before a single item was added - so one bad row emptied
        # the whole listing.
        items = self._generate([
            row(idhash='good1', title='Erste'),
            row(idhash='broken', title='Kaputt', url_video=''),
            row(idhash='good2', title='Zweite'),
        ])
        self.assertEqual([item[1].label for item in items],
                         ['Sendung: Erste', 'Sendung: Zweite'])

    def test_only_broken_films_yields_an_empty_but_finished_listing(self):
        items = self._generate([row(url_video='')])
        self.assertEqual(items, [])
        self.assertTrue(self.xbmcplugin.ended)


class GenerateListItemTest(unittest.TestCase):

    def setUp(self):
        support.install_kodi_stubs()
        self.plugin = support.Plugin()

    def test_returns_a_pair_of_nones_when_there_is_no_url(self):
        result = FilmlistUi(self.plugin)._generateListItem(_film(url_video=''))
        self.assertEqual(result, (None, None))

    def test_the_show_stays_out_of_the_films_own_title(self):
        # The label carries "Show: Title" because a flat list has to show
        # both; the title infolabel is the film's, and the show is where a
        # show belongs.
        (_, item) = FilmlistUi(self.plugin)._generateListItem(
            _film(title='Tagesschau', show='ARD aktuell'))
        self.assertEqual(item.label, 'ARD aktuell: Tagesschau')
        self.assertEqual(item.info['title'], 'Tagesschau')
        self.assertEqual(item.info['tvshowtitle'], 'ARD aktuell')

    def test_the_list_sorts_by_what_it_shows(self):
        # Sorting used to be told a lowercased copy of the label, which Kodi
        # compares case-insensitively anyway.
        (_, item) = FilmlistUi(self.plugin)._generateListItem(
            _film(title='Tagesschau', show='ARD aktuell'))
        self.assertEqual(item.info['sorttitle'], 'ARD aktuell: Tagesschau')

    def test_the_short_title_leaves_the_show_out_of_the_label(self):
        (_, item) = FilmlistUi(self.plugin, pLongTitle=False)._generateListItem(
            _film(title='Tagesschau', show='ARD aktuell'))
        self.assertEqual(item.label, 'Tagesschau')
        self.assertEqual(item.info['title'], 'Tagesschau')

    def test_the_channel_is_the_studio(self):
        # It reached the screen only as an icon, which is no help to anyone
        # whose skin does not show one, and nothing to search or sort by.
        (_, item) = FilmlistUi(self.plugin)._generateListItem(_film(channel='ZDF'))
        self.assertEqual(item.info['studio'], 'ZDF')

    def test_a_subtitle_is_announced_as_a_stream(self):
        # Whether a film has subtitles was only findable by opening the
        # context menu.
        (_, item) = FilmlistUi(self.plugin)._generateListItem(
            _film(url_sub='https://example.org/a.ttml'))
        self.assertEqual(item.streams, [('subtitle', {'language': 'de'})])

    def test_a_film_without_subtitles_announces_none(self):
        (_, item) = FilmlistUi(self.plugin)._generateListItem(_film(url_sub=''))
        self.assertEqual(item.streams, [])

    def test_prefers_sd_over_the_plain_url(self):
        (url, _) = FilmlistUi(self.plugin)._generateListItem(
            _film(url_video='https://example.org/a.mp4',
                  url_video_sd='https://example.org/sd.mp4'))
        self.assertEqual(url, 'https://example.org/sd.mp4')


class AiredDateTest(unittest.TestCase):
    """The film list stores the broadcast time as a Unix timestamp.

    Kodi expects the info labels in local time, and the addon used to build
    them from datetime.fromtimestamp(0) plus the timestamp. That base carries
    the offset in force on 1 January 1970, so every broadcast in summer time
    came out an hour early.
    """

    def setUp(self):
        support.install_kodi_stubs()
        self.plugin = support.Plugin()

    def _info(self, aired):
        (_, item) = FilmlistUi(self.plugin)._generateListItem(_film(aired=aired))
        return item.info

    def test_the_plot_is_the_description_alone(self):
        # The aired date used to be pasted in front of it in an ISO format,
        # while date, aired and dateadded were carrying it as well.
        info = self._info(1704110400)
        self.assertEqual(info['plot'], '')
        (_, item) = FilmlistUi(self.plugin)._generateListItem(
            _film(description='Worum es geht.', aired=1704110400))
        self.assertEqual(item.info['plot'], 'Worum es geht.')

    @unittest.skipUnless(hasattr(time, 'tzset'), 'needs a POSIX timezone')
    def test_summer_time_keeps_the_day(self):
        # 2024-07-01 00:30 CEST, half an hour into the day in Berlin.
        with _timezone('Europe/Berlin'):
            info = self._info(calendar.timegm((2024, 6, 30, 22, 30, 0, 0, 0, 0)))
        self.assertEqual(info['date'], '2024-07-01')
        self.assertTrue(info['dateadded'].startswith('2024-07-01 00:30'),
                        info['dateadded'])

    @unittest.skipUnless(hasattr(time, 'tzset'), 'needs a POSIX timezone')
    def test_winter_time_is_unchanged(self):
        # 2024-01-15 13:00 CET.
        with _timezone('Europe/Berlin'):
            info = self._info(calendar.timegm((2024, 1, 15, 12, 0, 0, 0, 0, 0)))
        self.assertEqual(info['date'], '2024-01-15')
        self.assertTrue(info['dateadded'].startswith('2024-01-15 13:00'),
                        info['dateadded'])


@contextlib.contextmanager
def _timezone(name):
    previous = os.environ.get('TZ')
    os.environ['TZ'] = name
    time.tzset()
    try:
        yield
    finally:
        if previous is None:
            del os.environ['TZ']
        else:
            os.environ['TZ'] = previous
        time.tzset()


def _film(**kwargs):
    from resources.lib.model.film import Film
    film = Film()
    film.init(*row(**kwargs))
    return film


if __name__ == '__main__':
    unittest.main()
