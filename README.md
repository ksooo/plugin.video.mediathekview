Kodi Addon MediathekView+
=========================

**This add-on is based on the code of https://github.com/mediathekview/plugin.video.mediathekview.**
It is a fork maintained by Kai Sommerfeld with its own add-on ID
(`plugin.video.mediathekview.ksooo`), created because the original add-on has
not been maintained for a long time. Please report bugs and feature requests
for this fork here as a [GitHub Issue][3] only, not to the original project.

[1]: https://forum.mediathekview.de/category/14/offizieller-client-kodi-add-on
[2]: https://forum.kodi.tv/showthread.php?tid=326799
[3]: https://github.com/ksooo/plugin.video.mediathekview/issues
[4]: https://github.com/ksooo/plugin.video.mediathekview
[5]: https://github.com/mediathekview/plugin.video.mediathekview
[6]: https://github.com/mediathekview/kodi-repos

About this Addon
----------------

Yet another Kodi Addon for the German public service video platforms... Why?

Because the approach of this addon is different from that of the already
available addons: this addon uses the database of the popular project
_"MediathekView"_, which is updated hourly and contains more than 200,000
entries from all German public service video platforms. This approach has
some significant advantages over the other addons that usually scan the
ever-changing websites of the German public service video platforms:

* High speed browsing and navigation
* Independence from all changes to the page layout of the media libraries
* High reliability

Errors and feature requests concerning this fork can be reported as a
[GitHub Issue][3]. The source code is available on [GitHub][4]. The forums of
the original project ([German forum topic][1], [Kodi Addon Forum topic][2])
refer to the [original addon][5] and not to this fork.


Highlights
----------
* Background updating of the database
* Amazing fast navigation and search
* Download with subtitles and automatic NFO file generation
* Internal standalone or shared MySQL database support
* UI localised to German and English


How it Works
------------

The addon downloads the database from MediathekView and imports it either into
a local SQLite database, or alternatively into a local or remote MySQL database
(for use by multiple Kodi clients).
During the runtime of Kodi, only the differential update files are downloaded
from MediathekView in a configurable interval (default: 2 hours) and integrated
into the database. By the next calendar day after the last update at the latest,
the update will be carried out again by importing the full MediathekView
database.


System Requirements
-------------------

The system requirements for the addon vary depending on the configuration.
After installation, the addon starts in local mode: this means that a local
SQLite database is used, which is also updated locally by the Kodi system.
This is probably the most common scenario.

Ideally, using the local database requires a file system with a decent
performance. A Raspberry with a slow SD card is certainly not the very
best choice in this case but still acceptable. The full update will take
in this case about 15-20 minutes but since this happens in the background,
you may be able to live with it.

The addon has been tested on different platforms under Linux, MacOS,
Windows and LibreELEC/OpenELEC. Various Android systems have also been
tested successfully. Due to the variety of platforms, however, it is not
possible to make a final compatibility statement.


Install
-------

This fork is not offered through any official Kodi repository. To install it,
download the source code from [GitHub][4] as a ZIP file and install it in Kodi
via _"Add-ons > Install from zip file"_. Updates have to be installed manually
the same way.

The original addon is still offered through the [MediathekView
repositories][6]. Both addons have different IDs
(`plugin.video.mediathekview` and `plugin.video.mediathekview.ksooo`) and can
therefore be installed side by side; in Kodi they show up as
_"MediathekView"_ and _"MediathekView+"_. Settings and the local
database are separate; an external MySQL database however is shared if both
are configured to use the same server and database name.


How the update methods work
---------------------------

The addon supports 5 different update methods:
* **Continuously:** With this method the update takes place once per set
update interval (default: 2 hours). The first update of a calendar day is a
full update, all others are differential updates.
* **Automatic (Default):** This method automatically updates the database.
The update takes place once per set update interval (default: 2 hours). The
first update of a calendar day is a full update, all others are differential
updates. The auto-update pauses if the addon has not been used for more than
2 hours to save bandwidth and power on mobile devices.
* **On Start:** An update will only take place on the start of the addon.
If this is the first update of the day, it is a complete update, otherwise a
differential one. All further updates must be manually initiated by the user
via the main menu.
* **Manual:** There is no automatic update. The user has the possibility to
initiate updates via the main menu. If this is the first update of the day,
it is a complete update, otherwise a differential one.
* **Disabled:** There is no automatic update. This configuration only makes
sense if the plugin uses an external database and this database is updated
elsewhere.


Alternate Configurations
------------------------

If the Kodi system is too slow to manage its own database (e.g. Raspberry PI
with a very slow SD card) or you want to share the database across multiple
Kodi instances, it is also possible to use the addon with an external database
server (MySQL or MariaDB).

Since many Kodi users have their own NAS system to make their media available
to the media center, this is usually also suitable as a MySQL/MariaDB database
server since almost all NAS operating systems offer the installation of MySQL.

If the addon is configured to use a MySQL/MariaDB database, the database is
created automatically if it does not yet exist on the database server. However,
the specified database user must also have sufficient user rights in order to
do this.

The connection to the database can be configured in the addon settings in
the _"Database Settings"_ section.

At least one of the connected Kodi systems has to be able to update the
database; the data is then available to all of them. Set the update method of
the others to *Disabled* so they only read.
