# -*- coding: utf-8 -*-
"""
The season and episode numbers the film list keeps inside its titles

SPDX-License-Identifier: MIT
"""

# -- Imports ------------------------------------------------
import re

# -- Constants ----------------------------------------------
# MediathekView leaves the season and episode inside the title, in the one
# shape it is consistent about: "(S01/E11)" or "(S2024E80)". 57150 of 715993
# films carry it. The other forms it uses - "Folge 6", "(1/4)", "Teil 2" -
# are fewer and ambiguous, "(1/4)" as often meaning part one of four, so they
# are left where they are.
EPISODE_MARKER = re.compile(r'\s*\(\s*S(\d{1,4})\s*/?\s*E(\d{1,4})\s*\)\s*', re.I)
# What a show has to look like before its films are put behind seasons.
#
# Of 11209 shows, 1987 carry episode numbers at all, but 1383 of those have a
# single season, where the extra level would be a click for nothing. Of the
# 604 that have more, a good hundred are daily formats where the numbering is
# the exception rather than the rule - "heute 19:00 Uhr" has 4851 films, 2604
# of them unnumbered - and those are better left flat. Asking for four in
# five leaves 473 shows, which are the series: In aller Freundschaft, Die
# Rosenheim-Cops, Der Bergdoktor, Löwenzahn.
MINIMUM_SEASONS = 2
MINIMUM_MARKED_SHARE = 0.8
# Where the title sits in a row of the film query.
TITLE = 1


# -- Functions ----------------------------------------------
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


def seasonOf(row):
    """ The season the film's title names, or `None` """
    match = EPISODE_MARKER.search(row[TITLE] or '')
    return int(match.group(1)) if match else None


def group(rows):
    """
    Sorts the films of one show into seasons.

    Returns the seasons in order, each as a (number, films) pair, and the
    films that name no season. A show that does not earn a season level -
    see the constants above - comes back as no seasons at all and every film
    loose, which is the flat listing it had before.
    """
    seasons = {}
    loose = []
    for row in rows:
        season = seasonOf(row)
        if season is None:
            loose.append(row)
        else:
            seasons.setdefault(season, []).append(row)
    marked = len(rows) - len(loose)
    if (len(seasons) < MINIMUM_SEASONS or
            marked < MINIMUM_MARKED_SHARE * len(rows)):
        return ([], list(rows))
    return (sorted(seasons.items()), loose)


def ofSeason(rows, season):
    """ The films of one season """
    return [row for row in rows if seasonOf(row) == season]
