# -*- coding: utf-8 -*-
"""
The addon settings module

Copyright 2017-2018, Leo Moll and Dominik Schlösser
SPDX-License-Identifier: MIT
"""

# -- Imports ------------------------------------------------
import time
# pylint: disable=import-error
import xbmc
import xbmcvfs
import resources.lib.mvutils as mvutils
from resources.lib.settingsInterface import SettingsInterface
# -- Classes ------------------------------------------------


class SettingsKodi(SettingsInterface):
    """ The settings class """

    def __init__(self, pAddonClass):
        xbmc.log("SettingsKodi:init", xbmc.LOGDEBUG)
        self._addonClass = pAddonClass
        pass

    def _getInt(self, settingId, default):
        """
        Reads a setting as a number, falling back to `default`.

        A setting Kodi could not read comes back as an empty string, and a
        plain int() on that ends the plugin or the service before either can
        say anything. Whatever went wrong, carrying on with the declared
        default beats not starting at all.

        The defaults repeat what resources/settings.xml declares;
        tests/test_settings.py holds the two against each other.
        """
        value = self._addonClass.getSetting(settingId)
        try:
            return int(float(value))
        except (TypeError, ValueError):
            xbmc.log('[{}] setting "{}" is unreadable ({!r}), using {}'.format(
                self._addonClass.getAddonInfo('id'), settingId, value, default),
                xbmc.LOGERROR)
            return default

    # self.datapath
    def getDatapath(self):
        if self.getKodiVersion() > 18:
            return mvutils.py2_decode(xbmcvfs.translatePath(self._addonClass.getAddonInfo('profile')))
        else:
            return mvutils.py2_decode(xbmc.translatePath(self._addonClass.getAddonInfo('profile')))

    def getKodiVersion(self):
        """
        Get Kodi major version
        Returns:
            int: Kodi major version (e.g. 18)
        """
        xbmc_version = xbmc.getInfoLabel("System.BuildVersion")

        return int(xbmc_version.split('-')[0].split('.')[0])

    # General
    # self.preferhd
    def getPreferHd(self):
        return self._addonClass.getSetting('quality') == 'true'

    # self.autosub
    def getAutoSub(self):
        return self._addonClass.getSetting('autosub') == 'true'

    # self.nofuture
    def getNoFutur(self):
        return self._addonClass.getSetting('nofuture') == 'true'

    # self.hideaudiodescription
    def getHideAudioDescription(self):
        return self._addonClass.getSetting('hideaudiodescription') == 'true'

    # self.minlength
    def getMinLength(self):
        return self._getInt('minlength', 0)

    # self.groupshows
    def getGroupShow(self):
        return self._addonClass.getSetting('groupshows') == 'true'

    # self.maxresults
    def getMaxResults(self):
        return self._getInt('maxresults', 1000)

    # self.maxage
    def getMaxAge(self):
        return self._getInt('maxage', 2) * 86400

    # self.recentmode
    def getRecentMode(self):
        return self._getInt('recentmode', 0)

    # self.filmSortMethod
    def getFilmSortMethod(self):
        return self._getInt('filmuisortmethod', 0)

    # self.updateCheckInterval
    def getUpdateCheckIntervel(self):
        return self._getInt('updateCheckInterval', 30)

    def getDatabaseImportBatchSize(self):
        return self._getInt('updateBatchSize', 10000)

    def getBlacklist(self):
        return self._addonClass.getSetting('blacklist')

    def getTmdbEnabled(self):
        return self._addonClass.getSetting('tmdbEnabled') == 'true'

    def getTmdbToken(self):
        return self._addonClass.getSetting('tmdbToken').strip()


    # Database

    # self.type
    def getDatabaseType(self):
        return self._getInt('dbtype', 0)

    # self.host
    def getDatabaseHost(self):
        return self._addonClass.getSetting('dbhost')

    # self.port
    def getDatabasePort(self):
        return self._getInt('dbport', 3306)

    # self.user
    def getDatabaseUser(self):
        return self._addonClass.getSetting('dbuser')

    # self.password
    def getDatabasePassword(self):
        return self._addonClass.getSetting('dbpass')

    # self.database
    def getDatabaseSchema(self):
        return self._addonClass.getSetting('dbdata')

    # self.updmode
    def getDatabaseUpateMode(self):
        return self._getInt('updmode', 3)

    # self.updnative
    def getDatabaseUpdateNative(self):
        return self._addonClass.getSetting('updnative') == 'true'

    # self.caching
    def getCaching(self):
        return self._addonClass.getSetting('caching') == 'true'

    # self.updinterval
    def getDatabaseUpdateInvterval(self):
        return self._getInt('updinterval', 2) * 3600

    # Download

    # self.downloadpathep
    def getDownloadPathEpisode(self):
        return mvutils.py2_decode(self._addonClass.getSetting('downloadpathep'))

    # self.downloadpathmv
    def getDownloadPathMovie(self):
        return mvutils.py2_decode(self._addonClass.getSetting('downloadpathmv'))

    # self.moviefolders
    def getUseMovieFolder(self):
        return self._addonClass.getSetting('moviefolders') == 'true'

    # self.movienamewithshow
    def getMovieNameWithShow(self):
        return self._addonClass.getSetting('movienamewithshow') == 'true'

    # self.reviewname
    def getReviewName(self):
        return self._addonClass.getSetting('reviewname') == 'true'

    # self.downloadsrt
    def getDownloadSubtitle(self):
        return self._addonClass.getSetting('downloadsrt') == 'true'

    # self.makenfo
    def getMakeInfo(self):
        return self._getInt('makenfo', 2)

    # prompt / keep / overwrite
    def getFileExistsAction(self):
        return self._getInt('fileExistsAction', 0)

    # low / med / high
    def getDownloadQuality(self):
        return self._getInt('downloadQuality', 0)

    # RUNTIME
    def is_update_triggered(self):
        return self._addonClass.getSetting('updatetrigger') == 'true'

    def set_update_triggered(self, aValue):
        self._addonClass.setSetting('updatetrigger', aValue)

    def getLastFullUpdate(self):
       return self._getInt('lastFullUpdate', 0)

    def setLastFullUpdate(self, aLastFullUpdate):
        self._addonClass.setSetting('lastFullUpdate', str(aLastFullUpdate))

    def getLastUpdate(self):
        return self._getInt('lastUpdate', 0)

    def setLastUpdate(self, aLastUpdate):
        self._addonClass.setSetting('lastUpdate', str(aLastUpdate))

    def getDatabaseStatus(self):
        return self._addonClass.getSetting('databaseStatus')

    def setDatabaseStatus(self, aStatus):
        self._addonClass.setSetting('databaseStatus', aStatus)

    def getDatabaseVersion(self):
        return self._getInt('databaseVersion', 0)

    def setDatabaseVersion(self, aVersion):
        self._addonClass.setSetting('databaseVersion', str(aVersion))

    def is_user_alive(self):
        """ Returns `True` if there was recent user activity """
        return int(time.time()) - self._getInt('lastactivity', 0) < 7200

    def user_activity(self):
        """ Signals that a user activity has occurred """
        if not(self.is_user_alive()):
            self._addonClass.setSetting('lastactivity', '{}'.format(int(time.time())))

    def getUserAgentString(self):
        return self._addonClass.getSetting('userAgentString')

    def getDelayStartupSec(self):
        return self._getInt('delayStartupSec', 10)

