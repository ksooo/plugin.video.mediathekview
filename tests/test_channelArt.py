# -*- coding: utf-8 -*-
"""
Tests for the artwork of a channel

SPDX-License-Identifier: MIT
"""

import os
import unittest

from tests import support

support.init_app_context()

import resources.lib.appContext as appContext
from resources.lib.ui.channelArt import artFor

SENDER = os.path.join(support.ADDON_PATH, 'resources', 'icons', 'sender')


class ArtForTest(unittest.TestCase):

    def setUp(self):
        support.init_app_context()

    def test_a_channel_gets_its_own_artwork(self):
        (icon, fanart) = artFor(support.ADDON_PATH, 'ZDF')
        self.assertTrue(icon.endswith(os.path.join('sender', 'zdf-i.png')), icon)
        self.assertTrue(fanart.endswith(os.path.join('sender', 'zdf-f.png')), fanart)

    def test_the_name_is_taken_as_it_comes(self):
        # The files are named after the channel in lower case.
        (icon, _) = artFor(support.ADDON_PATH, 'ARD-alpha')
        self.assertTrue(icon.endswith('ard-alpha-i.png'), icon)

    def test_a_channel_nobody_drew_gets_a_generic_one(self):
        # An item with no artwork at all reads as a broken item.
        (icon, fanart) = artFor(support.ADDON_PATH, 'Kanal Ohne Logo')
        self.assertTrue(icon.endswith('broadcast-m.png'), icon)
        self.assertTrue(fanart.endswith('broadcast-f.png'), fanart)

    def test_it_says_so_when_it_falls_back(self):
        # Otherwise a channel MediathekView adds turns up blank and unnoticed.
        artFor(support.ADDON_PATH, 'Kanal Ohne Logo')
        logged = [text for (level, text) in appContext.MVLOGGER.messages]
        self.assertTrue(any('Kanal Ohne Logo' in text for text in logged), logged)

    def test_the_artwork_it_falls_back_to_is_really_there(self):
        (icon, fanart) = artFor(support.ADDON_PATH, 'Kanal Ohne Logo')
        self.assertTrue(os.path.exists(icon), icon)
        self.assertTrue(os.path.exists(fanart), fanart)


class ArtworkOnDiskTest(unittest.TestCase):
    """The files themselves.

    tagesschau24, ZDFinfo and ZDFneo showed no logo for 13447 films, while
    their artwork sat in the livestream folder under a different spelling.
    """

    def test_the_channels_that_were_missing_have_their_artwork(self):
        for channel in ('tagesschau24', 'ZDFinfo', 'ZDFneo'):
            (icon, fanart) = artFor(support.ADDON_PATH, channel)
            self.assertTrue(icon.endswith(channel.lower() + '-i.png'), icon)
            self.assertTrue(os.path.exists(icon), icon)
            self.assertTrue(os.path.exists(fanart), fanart)

    def test_every_channel_icon_has_its_fanart(self):
        names = os.listdir(SENDER)
        icons = sorted(name[:-6] for name in names if name.endswith('-i.png'))
        fanarts = sorted(name[:-6] for name in names if name.endswith('-f.png'))
        self.assertEqual(icons, fanarts)


if __name__ == '__main__':
    unittest.main()
