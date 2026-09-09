# -*- coding: utf-8 -*-
"""
The accessibility versions the film list carries beside the film itself

SPDX-License-Identifier: MIT
"""

# -- Imports ------------------------------------------------
import re

# -- Constants ----------------------------------------------
# How the broadcasters mark a version, always at the end of the title. The
# short forms are only accepted in brackets, since a title could end in two
# capitals by accident. Counted over the 715965 films of one list: 16625 end
# in "Audiodeskription", 892 in "Hörfassung", which is the same thing under
# an older name, 80 in "(AD)", and 10826 mark sign language.
AUDIO_DESCRIPTION = (
    re.compile(r'\s*[\(\[]?\s*(?:mit\s+)?(?:Audiodeskription|Hörfassung)\s*[\)\]]?\s*$',
               re.I),
    re.compile(r'\s*[\(\[]\s*AD\s*[\)\]]\s*$'))
SIGN_LANGUAGE = (
    re.compile(r'\s*[\(\[]?\s*(?:mit\s+|in\s+)?Gebärdensprache\s*[\)\]]?\s*$', re.I),
    re.compile(r'\s*[\(\[]\s*DGS\s*[\)\]]\s*$'))
# Some titles hang the marker on with a separator - "Der Fall (1/2) -
# Audiodeskription" - and leaving that behind finds a thousand fewer twins.
TRAILING_SEPARATOR = re.compile(r'[-–—|,:]\s*$')
# Where the fields of a film query sit.
TITLE = 1
SHOWNAME = 2
CHANNEL = 3


# -- Functions ----------------------------------------------
def plainTitle(title, markers=AUDIO_DESCRIPTION):
    """ The title without the marker of that version, or `None` """
    for marker in markers:
        if marker.search(title or ''):
            plain = marker.sub('', title).strip()
            return TRAILING_SEPARATOR.sub('', plain).strip()
    return None


def without(rows, markers):
    """
    Drops the marked films that are listed beside the film itself.

    A version that is the only one there is stays, whoever wants it. The
    comparison is against the films of this listing, which is what "beside"
    means. Of one list's 17597 films marked as audio described 16215 have
    such a twin, and of the 10826 marked as sign language 8427 do.
    """
    present = set((row[CHANNEL], row[SHOWNAME], row[TITLE]) for row in rows)
    kept = []
    for row in rows:
        plain = plainTitle(row[TITLE], markers)
        if plain is None or (row[CHANNEL], row[SHOWNAME], plain) not in present:
            kept.append(row)
    return kept


def withoutAudioDescription(rows):
    """ Drops the audio described films listed beside the film itself """
    return without(rows, AUDIO_DESCRIPTION)


def withoutSignLanguage(rows):
    """ Drops the sign language films listed beside the film itself """
    return without(rows, SIGN_LANGUAGE)
