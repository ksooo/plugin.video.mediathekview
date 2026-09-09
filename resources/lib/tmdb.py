# -*- coding: utf-8 -*-
"""
What themoviedb.org knows about a show

SPDX-License-Identifier: MIT
"""

# -- Imports ------------------------------------------------
import json
import re
import unicodedata

# pylint: disable=import-error
try:
    # Python 3.x
    from urllib.error import HTTPError, URLError
    from urllib.parse import quote
    from urllib.request import Request, urlopen
except ImportError:
    # Python 2.x
    from urllib2 import HTTPError, URLError, Request, urlopen
    from urllib import quote

import resources.lib.appContext as appContext

# -- Constants ----------------------------------------------
BASE_URL = 'https://api.themoviedb.org/3'
# The image server needs no credentials of any kind, so a stored url keeps
# working even after the token is taken out of the settings.
IMAGE_URL = 'https://image.tmdb.org/t/p/'
POSTER_SIZE = 'w500'
FANART_SIZE = 'w1280'
# An episode still is a wide picture of a scene, shown where a list shows
# thumbnails, so it needs neither poster nor fanart proportions.
STILL_SIZE = 'w300'
# Everything the film list carries is German, whatever language the interface
# is set to, so German is the right thing to ask for.
LANGUAGE = 'de-DE'
COUNTRY = 'DE'
# How many search results are considered. Measured over 358 shows: taking the
# first three finds six more than taking only the first, and a fourth or
# fifth finds nothing at all.
SEARCH_DEPTH = 3
# A listing waits for this, twice at worst - once to search, once for the
# details - so it has to be short enough to be bearable and long enough for
# a mobile connection.
TIMEOUT = 4

# Every kind of dash is written differently in the two databases.
_DASHES = dict.fromkeys(map(ord, '‐‑‒–—―'), '-')
_QUOTES = re.compile(r'["“”„‘’\']')
_SEPARATORS = (' - ', ': ')


# -- Matching -----------------------------------------------
def _plain(name):
    """ Lower case, one kind of dash, no quotes, single spaces """
    name = unicodedata.normalize('NFC', name or '').lower().translate(_DASHES)
    return re.sub(r'\s+', ' ', _QUOTES.sub('', name)).strip()


def _loose(name):
    """ As above, and separators and trailing dots stop counting """
    name = re.sub(r'[-:]', ' ', _plain(name))
    return re.sub(r'\s+', ' ', re.sub(r'[.…]+$', '', name)).strip()


def matches(ours, theirs):
    """
    Says how a show name of ours relates to one of theirs, or `None`.

    Two tiers, because one alone is either too strict or too loose. Equality
    is judged on the loose form, which lets "Die Heiland - Wir sind Anwalt"
    meet "Die Heiland: Wir sind Anwalt" and "Sketch-History" meet "Sketch
    History". A longer name of theirs is only accepted when ours is cut off
    at a real separator, which is what lets "Morden im Norden" meet "Heiter
    bis toedlich - Morden im Norden" while keeping "Bolzplatz" away from
    "Bolzplatz-Duell".
    """
    if _loose(ours) == _loose(theirs):
        return 'equal'
    (ourPlain, theirPlain) = (_plain(ours), _plain(theirs))
    for separator in _SEPARATORS:
        if theirPlain.startswith(ourPlain + separator):
            return 'prefix'
        if theirPlain.endswith(separator + ourPlain):
            return 'suffix'
    return None


def pick(showname, results):
    """ The first of the results that the name allows, or `None` """
    for result in (results or [])[:SEARCH_DEPTH]:
        if matches(showname, result.get('name') or ''):
            return result
    return None


# -- Classes ------------------------------------------------
class Tmdb(object):
    """ The themoviedb.org client """

    def __init__(self):
        self.logger = appContext.MVLOGGER.get_new_logger('Tmdb')
        self.settings = appContext.MVSETTINGS

    def available(self):
        """ Whether asking is switched on and there is something to ask with """
        return bool(self.settings.getTmdbEnabled() and self.settings.getTmdbToken())

    def lookupShow(self, showname):
        """
        Everything the service has on a show, or `None`.

        `None` means the service was asked and had nothing to offer, or could
        not be reached - the caller cannot tell those apart and does not need
        to. Two requests: one to find the show, one for its details, which
        carry the season posters along.
        """
        found = pick(showname, self._search(showname))
        if found is None:
            return None
        details = self._details(found['id'])
        if details is None:
            return None
        return self._record(details)

    def lookupSeason(self, tmdbid, season):
        """
        The still of every episode of one season that has one.

        One request for the whole season. Whether the episodes carry stills
        varies by programme rather than by chance: Die Rosenheim-Cops has one
        for all 24 episodes of a season, In aller Freundschaft has none for
        any of its 42.
        """
        answer = self._get('/tv/%d/season/%d' % (tmdbid, season),
                           missingIsAnswer=True)
        if answer is None:
            return None
        stills = {}
        for episode in answer.get('episodes') or []:
            number = episode.get('episode_number')
            still = self._image(episode.get('still_path'), STILL_SIZE)
            if number is not None and still:
                stills[number] = still
        return stills

    # -- Internals ------------------------------------------
    def _search(self, showname):
        answer = self._get('/search/tv', 'query=' + quote(showname.encode('utf-8')))
        return (answer or {}).get('results') or []

    def _details(self, tmdbid):
        return self._get('/tv/%d' % tmdbid,
                         'append_to_response=content_ratings,external_ids')

    def _record(self, details):
        """ The fields to keep, in the shape the store holds them """
        externals = details.get('external_ids') or {}
        return {
            'tmdbid': details.get('id'),
            'poster': self._image(details.get('poster_path'), POSTER_SIZE),
            'fanart': self._image(details.get('backdrop_path'), FANART_SIZE),
            'plot': (details.get('overview') or '').strip() or None,
            'genres': [genre['name'] for genre in details.get('genres') or []],
            'premiered': details.get('first_air_date') or None,
            'rating': details.get('vote_average') or None,
            'votes': details.get('vote_count') or None,
            'mpaa': self._rating(details),
            'imdbid': externals.get('imdb_id') or None,
            'seasons': self._seasons(details),
        }

    def _seasons(self, details):
        seasons = {}
        for season in details.get('seasons') or []:
            number = season.get('season_number')
            poster = self._image(season.get('poster_path'), POSTER_SIZE)
            plot = (season.get('overview') or '').strip() or None
            if number is not None and (poster or plot):
                seasons[number] = {'poster': poster, 'plot': plot}
        return seasons

    def _rating(self, details):
        """ The German age rating, which is an FSK one and reads better said so """
        for entry in (details.get('content_ratings') or {}).get('results') or []:
            if entry.get('iso_3166_1') == COUNTRY and entry.get('rating'):
                return 'FSK %s' % entry['rating']
        return None

    def _image(self, path, size):
        return IMAGE_URL + size + path if path else None

    def _get(self, path, query='', missingIsAnswer=False):
        """
        One request, or `None` if it did not work out.

        A read access token travels in the header, where no log will ever
        repeat it. An older v3 key has nowhere to go but the query string, so
        whoever pastes their debug log somewhere pastes their key with it -
        which is the reason to prefer the token.

        `missingIsAnswer` turns "there is no such thing" into an empty
        answer rather than a failure, so that the caller can remember it and
        stop asking. The film list names seasons TMDB does not have - Terra X
        has a season 2018 - and a quarter of them came back as 404.
        """
        token = self.settings.getTmdbToken()
        headers = {'Accept': 'application/json'}
        parameters = ['language=' + LANGUAGE]
        if query:
            parameters.append(query)
        if token.startswith('eyJ'):
            headers['Authorization'] = 'Bearer ' + token
        else:
            parameters.append('api_key=' + quote(token))
        url = '%s%s?%s' % (BASE_URL, path, '&'.join(parameters))
        # pylint: disable=broad-except
        try:
            request = Request(url, headers=headers)
            response = urlopen(request, timeout=TIMEOUT)
            try:
                return json.loads(response.read().decode('utf-8'))
            finally:
                response.close()
        except HTTPError as err:
            if missingIsAnswer and err.code == 404:
                return {}
            self.logger.error('TMDB request for {} failed: {}', path, err)
        except URLError as err:
            self.logger.error('TMDB request for {} failed: {}', path, err)
        except Exception as err:
            self.logger.error('TMDB answer for {} was unusable: {}', path, err)
        return None
