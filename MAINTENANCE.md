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
| Compression, in order of preference | `.xz` (needs the `xz` binary), `.bz2`, `.gz` |

Two things to watch here.

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

`resources/lib/ui/channelUi.py` builds the icon path from the channel name:
`resources/icons/sender/<channel lowercased>-i.png` for the icon and `-f.png`
for the fanart. There are 29 channels covered. A channel MediathekView adds or
renames gets no icon, and nothing reports it - the list entry simply appears
blank.

Livestreams work the same way from `resources/icons/livestream/`, covering 12
streams.

## Livestreams

`storeQuery.getLivestreams()` selects films whose *Thema* is exactly
`LIVESTREAM`. That is a convention of the film list, not a field of its own. If
MediathekView renames it, the livestream screen goes empty and no error is
raised.

## Kodi's side

`resources/lib/kodi/kodiaddon.py` maps view names onto **numeric view ids** per
skin: Estuary 55 and 500, Estouchy 500 and 550, Confluence 51, 504 and 500.
These are skin internals, not API. A skin reworking its views leaves the addon
selecting an unrelated one. The `staticViewIds` setting exists to switch the
whole mechanism off, which is the answer when it misbehaves.

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
