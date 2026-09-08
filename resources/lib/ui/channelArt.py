# -*- coding: utf-8 -*-
"""
The artwork of a channel

SPDX-License-Identifier: MIT
"""

# -- Imports ------------------------------------------------
import os

import resources.lib.appContext as appContext

# -- Constants ----------------------------------------------
# What a channel gets when nobody drew it a logo. MediathekView adds and
# renames channels, and an item with no artwork reads as a broken one - which
# is how tagesschau24, ZDFinfo and ZDFneo looked for 13447 films, their logos
# sitting in the livestream folder under a different spelling all along.
FALLBACK = 'broadcast'


# -- Functions ----------------------------------------------
def artFor(path, channel):
    """
    Returns the (icon, fanart) pair for a channel.

    Falls back to a generic one where the channel has no artwork of its own,
    and says so in the log, so that a channel MediathekView adds is noticed
    rather than turning up blank. Channels come with both files or with
    neither, so the icon decides for both.
    """
    icon = _sender(path, channel, '-i.png')
    if os.path.exists(icon):
        return (icon, _sender(path, channel, '-f.png'))
    appContext.MVLOGGER.get_new_logger('ChannelArt').debug(
        'No artwork for channel {}', channel)
    return (_generic(path, '-m.png'), _generic(path, '-f.png'))


def _sender(path, channel, suffix):
    return os.path.join(path, 'resources', 'icons', 'sender',
                        channel.lower() + suffix)


def _generic(path, suffix):
    return os.path.join(path, 'resources', 'icons', FALLBACK + suffix)
