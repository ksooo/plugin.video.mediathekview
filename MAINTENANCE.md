# Keeping up with MediathekView

The addon owns no data. Everything it shows comes from the film list that
MediathekView publishes, and every assumption it makes about that list is a
place where a change on their side can break this one. This note lists those
assumptions, because nothing here is validated: the addon does not check the
format it reads, so a change arrives as an exception during the update or, in
the worse cases, as a database that quietly fills with nonsense.

## Where the data comes from

`resources/lib/updateFileDownload.py`

| What | Value |
| --- | --- |
| Base address | `https://liste.mediathekview.de/` |
| Full list | `Filmliste-akt` |
| Differential list | `Filmliste-diff` |
| Prebuilt SQLite database | `filmliste-v3.db` |
| Compression, in order of preference | `.gz`, `.xz`, `.bz2` |

Three things to watch here.

The order follows what unpacking costs, not what the download costs.
Measured on the real archives, read in the same blocks the addon reads:
gzip 744 MB/s of unpacked output, xz 129, bzip2 69. The archive is the
largest of the three in exchange - 150 MB against 113 - and it never reaches
the disk, because the download is unpacked as it arrives. This used to look
for an `xz` executable, which Kodi does not ship while it does link liblzma,
so every Kodi ended up on bzip2, the slowest of the three.

The result is written no faster than `WRITE_BYTES_PER_SEC`, ten megabytes a
second. Unpacking bzip2 was slow enough to leave the storage room by
accident; asking for gzip took that room away and froze the interface for the
whole update, so the room is made on purpose now.

The full list is rejected below **200 MB** (`FullUpdate file size ... smaller
than allowed`). The check exists because a truncated download used to wipe the
database. It also means a genuinely smaller list from MediathekView would look
like a failure.

`filmliste-v3.db` is downloaded and put in place **as is** when the database
type is SQLite and *Fast Native Updates* is on. Its schema has to match what
`storeSqliteSetup.py` creates, because from then on this addon's queries run
against MediathekView's file. Nothing verifies that. The `v3` in the name is
the only handshake, and it is not checked either - only the `version` column
inside the database is, against the literal `3` in `updater.py`.

## How the film list is read

`resources/lib/updateFileImport.py`

The file is not parsed as JSON. It is split on the literal string `"X":` and
each piece is patched back into a JSON document by hand. That is a deliberate
trade - the list is hundreds of megabytes and a real parser was too slow - but
it means the format is pinned much harder than JSON would be.

**The update timestamp is read by byte offset.** `fileHeader[15:32]` cuts the
date out of the header. Any change to the header's opening bytes puts the cut
in the wrong place. The failure is silent: the date is unparseable, the
exception is caught, and the update carries on with no timestamp.

**Fields are addressed by position**, in the order MediathekView documents in
the header:

| Index | Field | Used as |
| --- | --- | --- |
| 0 | Sender | `channel` |
| 1 | Thema | `showname`, and `showid` = first 8 of its MD5 |
| 2 | Titel | `title`, truncated to 128 |
| 3, 4 | Datum, Zeit | parsed, then overwritten by index 16 |
| 5 | Dauer | `duration`, via `mvutils.make_duration` |
| 7 | Beschreibung | `description`, truncated to 1024 |
| 8 | Url | `url_video` |
| 10 | Url Untertitel | `url_sub` |
| 12 | Url Klein | `url_video_sd` |
| 14 | Url HD | `url_video_hd` |
| 16 | DatumL | `aired`, guarded against values past 2147483647 |
| 9, 18 | Website, Geo | parsed and then dropped |

An inserted or reordered field shifts everything after it. Titles would arrive
as dates, urls as descriptions. Nothing would raise.

**An empty Sender or Thema means "same as the previous record".** The list
leaves them out to save space, and the importer carries the last value
forward. A record arriving before any value has been seen would be filed under
an empty channel.

**The short and HD urls are relative to the main url.** `12` and `14` come as
`<count>|<suffix>`, meaning "take the first `<count>` characters of the main
url and append `<suffix>`". `_make_url` implements exactly that, and falls
back to using the value verbatim when there is no `|`.

**A film's identity is `md5(Sender + Thema + Titel + Url)`.** Change any of
those on MediathekView's side and the film is a new film: the old row is not
updated but left behind, to be removed by the next full update.

## The database

`resources/lib/storeSqliteSetup.py`, `resources/lib/storeMySqlSetup.py`

One denormalised `film` table and a `status` table, schema version `3`. The two
setup scripts are separate SQL and have to be kept in step by hand; only the
SQLite one has to additionally match the downloaded `filmliste-v3.db`.

`updater.py` compares the stored version against a literal `3`. Raising the
schema version means changing that literal, both setup scripts, and coming to
terms with the fact that `filmliste-v3.db` will still be v3.

## Channel icons

`resources/lib/ui/channelArt.py` builds the path from the channel name:
`resources/icons/sender/<channel lowercased>-i.png` for the icon and `-f.png`
for the fanart. All 31 channels the film list currently names are covered. A
channel MediathekView adds or renames falls back to the generic
`broadcast-m.png`, and says so in the log - it used to turn up blank and
unmentioned, which is how tagesschau24, ZDFinfo and ZDFneo went unnoticed
across 13447 films while their artwork sat in the livestream folder under a
different spelling.

The two folders hold the same kind of file and some of the same files, but
are keyed differently: `sender` by the channel name as the film list writes
it, `livestream` by the name `livestreamUi.py` maps each stream to. `ZDFinfo`
and `zdf.info` are the same logo under both rules.

Livestreams work the same way from `resources/icons/livestream/`, covering 12
streams.

## Livestreams

`storeQuery.getLivestreams()` selects films whose *Thema* is exactly
`LIVESTREAM`. That is a convention of the film list, not a field of its own. If
MediathekView renames it, the livestream screen goes empty and no error is
raised.

## themoviedb.org

`resources/lib/tmdb.py`, `resources/lib/metadata.py`,
`resources/lib/storeMetadata.py`

Off unless the user switches it on and pastes a token of their own. Nothing
here is required for the addon to work, and every failure - unreachable,
refused, unusable answer - comes back as "nothing known", which is what a
listing does with an unknown show anyway.

Two requests per show: `search/tv` to find it, then `tv/{id}` with
`append_to_response=content_ratings,external_ids`, which carries the season
posters in its own `seasons` array so they cost no further request. Both
together took between 0.17 and 0.78 seconds when measured. Asked in `de-DE`,
because everything the film list carries is German whatever the interface
speaks.

One request per season, `tv/{id}/season/{n}`, brings the picture of every
episode of it. Whether the episodes have pictures at all is a property of
the programme rather than of chance: measured over 40 of the seasons the
film list names, 14 had one for every episode and 12 for none - Die
Rosenheim-Cops has one for all 24 episodes of a season, In aller
Freundschaft for none of its 42.

Two answers have to be remembered rather than treated as failures, or the
same seasons are asked about on every pass. A season that brings no
pictures leaves no episode rows behind, so `season.checked` notes that it
was asked about. And a season TMDB does not have at all - the film list
names Terra X seasons by year, 10 of those 40 came back as 404 - is an
answer too, which is what `missingIsAnswer` in `_get` is for: only there,
because a 404 must not turn a show into an empty record.

Their terms ask for two things in return, and both are easy to lose in a
refactoring. The sentence "This product uses TMDB and the TMDB APIs but is
not endorsed, certified, or otherwise approved by TMDB" has to stand
prominently and in that wording: it is the `<disclaimer>` in `addon.xml`,
which Kodi shows across the bottom of the addon's information dialog
without anybody scrolling, and it is repeated in the help text of the
setting (#30998) and in the README. And their logo has to be shown, less
prominently than the addon's own: it is `resources/screenshot3.png`, their
own square mark on their own dark blue, unaltered.

Three things are pinned here that TMDB could move.

The image base address `https://image.tmdb.org/t/p/` and the sizes `w500`,
`w1280` and `w300` are written into the source. `/configuration` returns them, but
it needs a token like every other endpoint, and a stored image url has to
keep working after the token is taken out of the settings - which it does,
since the image server itself asks for nothing.

The German age rating is read from `content_ratings` where `iso_3166_1` is
`DE` and rendered as "FSK 6", because a bare "6" says nothing on screen.

And the match is made on the name and nothing else, because that is all
MediathekView gives us. The rule has two tiers and was calibrated against
the service rather than invented: all 358 shows the film list calls a series
were looked up and the answers kept, so it could be tried without asking
again. It accepts 234 of them. Two families are turned down on purpose - a
missing article ("Taunuskrimi" against "Der Taunuskrimi") and a name of ours
that is the longer one - because the same leniency accepts "Ermittler!" as
"Der Ermittler" and "Hubert und Staller" as "Hubert ohne Staller", which are
different programmes. Loosening it means measuring again, not guessing.

No listing asks the service. A plugin builds its listing in the moment it
is opened and the script then ends - there is no later moment at which an
item scrolling into view could be answered - and a channel listing holds up
to 1744 shows, which no user waits for. So `metadataPrefetch.py` looks the
shows up in the background service instead, twelve requests in flight and
held to 50 a second, five minutes per pass so that the service gets back to
the film database, until every show the film list names has an answer. It
then reads nothing more until a new film list arrives. A listing about one
show still asks for that one show, which is what covers a show the prefetch
has not reached yet.

Each stage logs one line when it starts and one when it stops, and nothing
per show: a debug line for every one of the 9208 shows drowned out the rest
of the log. What went wrong is still an error line.

The same pass runs behind the button in the settings, which hands it a
progress reporter - that is what makes Kodi show the bar in the corner - and
with one it is not cut short after five minutes, since nobody is waiting for
the film database while somebody watches a bar. The button closes the
settings dialog (`<close>true</close>`), because that dialog covers the bar:
the bar is a window of its own with `zorder 3` and the settings dialog
renders over it, dimming included.

Then the seasons, in a second stage of the same pass: every season the film
list names, read out of the titles because that is where the marker sits.
Of 3844 such seasons 2396 belong to a show TMDB knows, and those took two
minutes; measured against the live service, 40 seconds brought 720 seasons
and 3157 episode pictures. This is what a mixed listing needs - a search
can hold films of a hundred seasons, so it cannot fetch anything itself.

Every listing reads what is stored: a listing of shows and a mixed listing
of films - a search, or what was added lately - take the shows they hold
and their episode pictures in one query each, some 130 names in well under
a millisecond.

What it can find is limited, and by the data rather than by the rule: of the
first 1808 shows fetched, 764 were found on TMDB and 445 had a poster. The
rest are *Themen* nobody has an entry for - "kurz vor 5", "Landtag",
"Lammhüfte mit Zucchini und Minzpesto". Only the series index is asked;
measured over 120 of the misses, 16 do exist as a film on TMDB, which would
lift the share with a poster from a quarter to about a third at the price of
a third request for every miss.

`metadata.db` is a file of its own rather than a table in the film database,
for the same reason `dtCreated` says nothing there: with fast native updates
that database is MediathekView's own file, put in place as it comes. It
holds no housekeeping beyond a thirty-day memory for a miss. Measured over
the 96 shows of ZDFneo it costs 1.3 kilobytes per show including its
seasons, so some 12 MB once the prefetch has been through all 9221 shows
the current film list names.

## Which picture goes where

`resources/lib/ui/filmlistUi.py`

A film wears its own picture as `thumb` and no `poster`, which is how a
library episode is furnished. That is not squeamishness about the field
names - a skin takes the poster in preference to the episode's picture
wherever one is set (Estuary in `ShiftThumbVar`), so a poster on the film
would push its own picture off the screen.

The posters hang under the prefixed keys instead, `season.poster` and
`tvshow.poster`, again as Kodi does it. That is where the information
dialog looks for them - Estuary's `InfoDialogPosterVar` asks for `poster`,
then `season.poster`, then `tvshow.poster` - and it shows the poster with
the episode's own picture in front of it. Nothing else consults those keys,
so the listings are unaffected.

The film listing declares its content type as `episodes`, and that is what
decides how a skin lays the rows out. With a content type Estuary shows the
watched state in the row and no artwork, with an empty one the generic
layout with a picture per row - and it puts the picture of an `episode`
beside the list in a 16:9 frame rather than a poster frame
(`View_50_List.xml`, `ListThumbInfoPanel`).

It is written in the source, in `CONTENT_TYPE`. There used to be a setting
for it, *"Content Type Movie list"*, with five values and `none` as the
default, which is why every row carried a picture. What a listing holds is
not a matter of taste, and a changed default does not reach a profile that
already has the old one written down.

The listings of channels, letters, shows and livestreams declare no content
type on purpose. A show's poster belongs in its row, and that is the layout
that shows one.

## Kodi's side

The addon does not choose the view any more. It used to force one after every
listing, by numeric view id per skin - Estuary 55 and 500, Estouchy 500 and
550, Confluence 51, 504 and 500 - which are skin internals rather than API,
covered three skins out of all of them, and overruled the view Kodi remembers
for each path, so a view the user picked never survived going back. Kodi
keeps that memory itself; leave it alone.

`settingsKodi.py` and `kodiaddon.py` both branch on the Kodi major version to
choose between `xbmc.translatePath` and `xbmcvfs.translatePath`. The first was
removed in Kodi 20, so the branch is what keeps Kodi 19 working; it can go once
Kodi 19 is no longer supported.

## Subtitles

`ttml2srt.py` and `vtt2srt.py` convert what the broadcasters serve into SRT.
Both are regex-driven and taken from third-party projects. They handle what the
sampled broadcasters send, not the full specifications.

## Known dead ends

Left in place deliberately, so they do not come as a surprise:

* `updater.py` handles update mode `9`, labelled `mvupdate --full`. That mode
  was only ever set by the standalone commandline updater, which this fork
  removed. No setting can produce a `9` any more.
* The setting `lastsearch2` is declared and never read or written. Its sibling
  `lastsearch1` carries the quick search across playback.
* `Website` and `Geo` are read out of every film list record and then dropped.
  Geo-blocking information is therefore available but unused.
