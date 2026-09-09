# -*- coding: utf-8 -*-
"""
The accessibility versions the film list carries beside the film itself

SPDX-License-Identifier: MIT
"""

# -- Imports ------------------------------------------------
import re

# -- Constants ----------------------------------------------
# How the broadcasters mark an audio-described version, always at the end of
# the title. Of 715965 films 16625 are marked this way, 892 as "Hörfassung",
# which is the same thing under an older name, and 80 as "(AD)" - that one
# only in brackets, because a title could end in those two letters by
# accident.
AUDIO_DESCRIPTION = re.compile(
    r'\s*[\(\[]?\s*(?:mit\s+)?(?:Audiodeskription|Hörfassung)\s*[\)\]]?\s*$', re.I)
AUDIO_DESCRIPTION_SHORT = re.compile(r'\s*[\(\[]\s*AD\s*[\)\]]\s*$')
# Some titles hang the marker on with a separator - "Der Fall (1/2) -
# Audiodeskription" - and leaving that behind hides 843 fewer films.
TRAILING_SEPARATOR = re.compile(r'[-–—|,:]\s*$')
# Where the fields of a film query sit.
TITLE = 1
SHOWNAME = 2
CHANNEL = 3


# -- Functions ----------------------------------------------
def plainTitle(title):
    """ The title without its audio description marker, or `None` """
    for marker in (AUDIO_DESCRIPTION, AUDIO_DESCRIPTION_SHORT):
        if marker.search(title or ''):
            plain = marker.sub('', title).strip()
            return TRAILING_SEPARATOR.sub('', plain).strip()
    return None


def withoutAudioDescription(rows):
    """
    Drops the audio-described films that are listed beside the film itself.

    Of the 17597 films the current list marks, 16215 have such a twin. The
    other 1382 are the only version there is and stay, whoever wants them.
    The comparison is against the films of this listing, which is what
    "beside" means.
    """
    present = set((row[CHANNEL], row[SHOWNAME], row[TITLE]) for row in rows)
    kept = []
    for row in rows:
        plain = plainTitle(row[TITLE])
        if plain is None or (row[CHANNEL], row[SHOWNAME], plain) not in present:
            kept.append(row)
    return kept
