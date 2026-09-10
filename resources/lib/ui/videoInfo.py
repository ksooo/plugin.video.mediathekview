# -*- coding: utf-8 -*-
"""
What a list item says about a video

SPDX-License-Identifier: MIT
"""

# -- Constants ----------------------------------------------
# Which setter of InfoTagVideo each of our fields is written with. Kodi did
# this itself in ListItem.setInfo, which is deprecated since Kodi 20 and
# warns once per item - a listing of 53 films wrote 53 warnings into the log.
_TEXT = {
    'title': 'setTitle',
    'sorttitle': 'setSortTitle',
    'tvshowtitle': 'setTvShowTitle',
    'plot': 'setPlot',
    'mpaa': 'setMpaa',
    'premiered': 'setPremiered',
    'aired': 'setFirstAired',
    'dateadded': 'setDateAdded',
    'mediatype': 'setMediaType',
}
_NUMBER = {
    'season': 'setSeason',
    'episode': 'setEpisode',
    'duration': 'setDuration',
}
# These take a list, and a single value is one all the same.
_LIST = {
    'genre': 'setGenres',
    'studio': 'setStudios',
}


# -- Functions ----------------------------------------------
def apply(listitem, info):
    """
    Writes what we know about a video onto the item.

    Takes the fields ListItem.setInfo used to take, so that a caller reads
    the same as before. Unknown fields raise rather than pass unnoticed:
    setInfo swallowed them, and a typo would have been invisible.
    """
    tag = listitem.getVideoInfoTag()
    for (field, value) in info.items():
        if field in _TEXT:
            getattr(tag, _TEXT[field])(value)
        elif field in _NUMBER:
            getattr(tag, _NUMBER[field])(int(value))
        elif field in _LIST:
            getattr(tag, _LIST[field])(
                list(value) if isinstance(value, (list, tuple)) else [value])
        elif field == 'rating':
            tag.setRating(float(value), int(info.get('votes') or 0))
        elif field == 'votes':
            pass
        elif field == 'date':
            # The item's own date, which is what sorting by date reads. It
            # wants a W3C date, and a ten character one would be read as
            # day-month-year (ListItem::setDateTimeRaw).
            listitem.setDateTime(value)
        else:
            raise ValueError('unknown video info field %s' % field)
