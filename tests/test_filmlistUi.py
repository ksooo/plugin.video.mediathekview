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

from resources.lib.ui.filmlistUi import (FilmlistUi, LABEL_MASK_LONG,
                                         LABEL_MASK_SHORT)


def row(idhash='hash', title='Titel', show='Sendung', channel='ARD',
        description='', seconds=60, aired=0, url_sub='',
        url_video='https://example.org/a.mp4', url_video_sd='', url_video_hd='',
        showid='a1b2c3d4'):
    return (idhash, title, show, channel, description, seconds, aired,
            url_sub, url_video, url_video_sd, url_video_hd, showid)


class GenerateTest(unittest.TestCase):

    def setUp(self):
        self.xbmcplugin = support.install_kodi_stubs()
        self.plugin = support.Plugin()

    def _generate(self, rows):
        FilmlistUi(self.plugin).generate(rows)
        return self.xbmcplugin.items

    def test_it_says_what_the_listing_holds(self):
        # Which layout a skin gives the rows hangs on this: with a content
        # type it shows the watched state and no artwork in the row, with
        # none a picture per row.
        self._generate([row()])
        self.assertEqual(self.xbmcplugin.content, 'episodes')

    def test_lists_a_film(self):
        items = self._generate([row(title='Tagesschau')])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0][1].label, 'Sendung: Tagesschau')

    def test_the_list_is_told_how_to_build_its_labels(self):
        # Kodi rebuilds the label of a plugin item from the mask of the sort
        # method in force, so this is what the list shows - not the label the
        # item was given.
        self._generate([row()])
        self.assertEqual(set(self.xbmcplugin.label_masks), {LABEL_MASK_LONG})

    def test_a_listing_of_one_show_leaves_the_show_out_of_the_labels(self):
        FilmlistUi(self.plugin, pLongTitle=False).generate([row()])
        self.assertEqual(set(self.xbmcplugin.label_masks), {LABEL_MASK_SHORT})

    def test_episodes_can_be_sorted_by_their_number(self):
        self._generate([row()])
        self.assertIn(self.xbmcplugin.SORT_METHOD_EPISODE, self.xbmcplugin.sort_methods)

    def test_a_listing_of_one_show_is_offered_in_episode_order_first(self):
        # A whole season is published at one timestamp, so the date the query
        # sorts by cannot tell the episodes apart.
        FilmlistUi(self.plugin, pLongTitle=False).generate([row()])
        self.assertEqual(self.xbmcplugin.sort_methods[0],
                         self.xbmcplugin.SORT_METHOD_EPISODE)

    def test_a_listing_of_many_shows_keeps_the_sort_method_from_the_settings(self):
        self._generate([row()])
        self.assertEqual(self.xbmcplugin.sort_methods[0],
                         self.xbmcplugin.SORT_METHOD_UNSORTED)

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


class GoToShowTest(unittest.TestCase):
    """The entry that leads from a search result to the show it is from."""

    GO_TO_SHOW = 'Zur Sendung springen'

    def setUp(self):
        self.xbmcplugin = support.install_kodi_stubs()
        self.plugin = support.Plugin(strings={30132: self.GO_TO_SHOW})

    def _entries(self, longTitle=True, **fields):
        FilmlistUi(self.plugin, pLongTitle=longTitle).generate([row(**fields)])
        item = self.xbmcplugin.items[0][1]
        return ([entry[0] for entry in item.context_menu], item)

    def test_a_search_result_of_a_series_leads_to_its_show(self):
        (entries, _) = self._entries(title='Erben (S24/E02)')
        self.assertIn(self.GO_TO_SHOW, entries)

    def test_the_entry_names_the_show_and_the_film(self):
        (_, item) = self._entries(title='Erben (S24/E02)', channel='ZDF',
                                  showid='1c6953ff', idhash='deadbeef')
        command = [entry[1] for entry in item.context_menu
                   if entry[0] == self.GO_TO_SHOW][0]
        for expected in ('mode=gotoshow', 'channel=ZDF', 'show=1c6953ff',
                         'id=deadbeef'):
            self.assertIn(expected, command)

    def test_a_film_that_names_no_episode_has_nowhere_to_jump_to(self):
        (entries, _) = self._entries(title='Ein Sonderfall')
        self.assertNotIn(self.GO_TO_SHOW, entries)

    def test_the_listing_of_a_show_does_not_offer_it(self):
        # It would lead where the user already is.
        (entries, _) = self._entries(longTitle=False, title='Erben (S24/E02)')
        self.assertNotIn(self.GO_TO_SHOW, entries)

    def test_a_film_list_that_names_no_show(self):
        # Rows of the old shape, eleven columns, carry no show id.
        FilmlistUi(self.plugin).generate([row(title='Erben (S24/E02)')[:11]])
        entries = [entry[0] for entry in self.xbmcplugin.items[0][1].context_menu]
        self.assertNotIn(self.GO_TO_SHOW, entries)

    def test_the_film_says_which_one_it_is(self):
        # What the jump looks for once the listing is on screen.
        (_, item) = self._entries(idhash='deadbeef')
        self.assertEqual(item.properties['filmid'], 'deadbeef')


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

    def test_the_episode_marker_leaves_the_title_for_its_own_fields(self):
        (_, item) = FilmlistUi(self.plugin)._generateListItem(
            _film(title='Nordspanien von oben (S01/E11)', show='Europa von oben'))
        self.assertEqual(item.label, 'Europa von oben: Nordspanien von oben')
        self.assertEqual(item.info['title'], 'Nordspanien von oben')
        self.assertEqual(item.info['season'], 1)
        self.assertEqual(item.info['episode'], 11)
        self.assertEqual(item.info['mediatype'], 'episode')

    def test_a_film_that_is_not_an_episode_is_not_called_one(self):
        (_, item) = FilmlistUi(self.plugin)._generateListItem(_film(title='Tagesschau'))
        self.assertNotIn('season', item.info)
        self.assertNotIn('episode', item.info)
        self.assertNotIn('mediatype', item.info)

    def test_hd_is_a_resolution_rather_than_a_word_in_the_title(self):
        support.init_app_context(settings=support.Settings(preferHd=True))
        (_, item) = FilmlistUi(self.plugin)._generateListItem(
            _film(title='Tagesschau', url_video_hd='https://example.org/hd.mp4'))
        self.assertEqual(item.label, 'Sendung: Tagesschau')
        self.assertEqual(item.info['title'], 'Tagesschau')
        self.assertIn(('video', {'width': 1920, 'height': 1080}), item.streams)

    def test_nothing_is_claimed_about_a_stream_that_is_not_hd(self):
        # The film list says nothing about the other streams either, and a
        # made-up size would be a claim.
        (_, item) = FilmlistUi(self.plugin)._generateListItem(
            _film(url_video_sd='https://example.org/sd.mp4'))
        self.assertEqual([kind for (kind, _) in item.streams], [])

    def test_the_channel_is_the_studio(self):
        # It reached the screen only as an icon, which is no help to anyone
        # whose skin does not show one, and nothing to search or sort by.
        (_, item) = FilmlistUi(self.plugin)._generateListItem(_film(channel='ZDF'))
        self.assertEqual(item.info['studio'], ['ZDF'])

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
        self.plugin = support.Plugin(strings={30136: 'Sendetermin: {}'})

    def _info(self, aired):
        (_, item) = FilmlistUi(self.plugin)._generateListItem(_film(aired=aired))
        return item.info

    @unittest.skipUnless(hasattr(time, 'tzset'), 'needs a POSIX timezone')
    def test_the_plot_says_when_it_was_broadcast(self):
        # Kodi's own fields carry the broadcast as a date and drop the time
        # of day, and the description is the only text of ours a skin shows
        # beside a listing.
        with _timezone('Europe/Berlin'):
            (_, item) = FilmlistUi(self.plugin)._generateListItem(
                _film(description='Worum es geht.',
                      aired=calendar.timegm((2024, 1, 15, 12, 0, 0, 0, 0, 0))))
        self.assertEqual(item.info['plot'], 'Sendetermin: 15.01.2024 13:00\n\nWorum es geht.')

    @unittest.skipUnless(hasattr(time, 'tzset'), 'needs a POSIX timezone')
    def test_a_film_without_a_description(self):
        with _timezone('Europe/Berlin'):
            info = self._info(calendar.timegm((2024, 1, 15, 12, 0, 0, 0, 0, 0)))
        self.assertEqual(info['plot'], 'Sendetermin: 15.01.2024 13:00')

    def test_a_film_without_a_broadcast_time(self):
        (_, item) = FilmlistUi(self.plugin)._generateListItem(
            _film(description='Worum es geht.', aired=0))
        self.assertEqual(item.info['plot'], 'Worum es geht.')

    @unittest.skipUnless(hasattr(time, 'tzset'), 'needs a POSIX timezone')
    def test_the_region_settings_say_how_it_is_written(self):
        # And the seconds go: a broadcast is announced to the minute, while
        # Kodi's time format carries them.
        import xbmc
        self.addCleanup(setattr, xbmc, 'getRegion', xbmc.getRegion)
        xbmc.getRegion = lambda name: {'dateshort': '%m/%d/%Y',
                                       'time': '%I:%M:%S %p'}.get(name, '')
        with _timezone('Europe/Berlin'):
            info = self._info(calendar.timegm((2024, 1, 15, 12, 0, 0, 0, 0, 0)))
        self.assertEqual(info['plot'], 'Sendetermin: 01/15/2024 01:00 PM')

    @unittest.skipUnless(hasattr(time, 'tzset'), 'needs a POSIX timezone')
    def test_summer_time_keeps_the_day(self):
        # 2024-07-01 00:30 CEST, half an hour into the day in Berlin.
        with _timezone('Europe/Berlin'):
            info = self._info(calendar.timegm((2024, 6, 30, 22, 30, 0, 0, 0, 0)))
        self.assertEqual(info['date'], '2024-07-01T00:30:00')
        self.assertTrue(info['dateadded'].startswith('2024-07-01 00:30'),
                        info['dateadded'])

    @unittest.skipUnless(hasattr(time, 'tzset'), 'needs a POSIX timezone')
    def test_winter_time_is_unchanged(self):
        # 2024-01-15 13:00 CET.
        with _timezone('Europe/Berlin'):
            info = self._info(calendar.timegm((2024, 1, 15, 12, 0, 0, 0, 0, 0)))
        self.assertEqual(info['date'], '2024-01-15T13:00:00')
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
    # The show id is the row's last field and no part of the film itself.
    film.init(*row(**kwargs)[:11])
    return film


if __name__ == '__main__':
    unittest.main()
