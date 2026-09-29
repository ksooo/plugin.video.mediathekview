# -*- coding: utf-8 -*-
"""
Listings in pages, because a thousand films in one are no listing

SPDX-License-Identifier: MIT
"""

# -- Constants ----------------------------------------------
# A page of no size is a listing of everything.
UNPAGED = 0


# -- Functions ----------------------------------------------
def page(rows, offset, size):
    """
    The films of one page, and where the next one starts.

    Returns the rows to show and the offset of the page after them, or
    `None` where these were the last. Slicing happens before Kodi sorts the
    listing, so a page holds what the query put there rather than what the
    screen would show first - which is what lets a jump work out the page a
    film is on.
    """
    if size <= UNPAGED:
        return (list(rows), None)
    offset = max(0, offset)
    shown = list(rows[offset:offset + size])
    following = offset + size
    return (shown, following if following < len(rows) else None)


def pageOf(index, size):
    """ The offset of the page that holds the row at that position """
    if size <= UNPAGED or index < 0:
        return 0
    return (index // size) * size
