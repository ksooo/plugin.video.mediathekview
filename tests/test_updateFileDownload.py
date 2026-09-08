# -*- coding: utf-8 -*-
"""
Tests for what the screen says while the database update runs

SPDX-License-Identifier: MIT
"""

import bz2
import gzip
import os
import shutil
import tempfile
import unittest

from tests import support

support.init_app_context()

from resources.lib.updateFileDownload import UpdateFileDownload

_PAYLOAD = b'{"Filmliste":["30.08.2020, 11:13"]}\n' * 4096
# Something that does not compress, so the packed file runs to many more than
# the 8 KB the unpacking reads at a time and the bar has room to move.
_INCOMPRESSIBLE = os.urandom(200000)


class UnpackProgressTest(unittest.TestCase):
    """The dialog has to say which half of the update is running.

    It used to sit at "downloading, 100%" for as long as the unpacking took,
    which on Android is the longer half - a minute of a dialog claiming to be
    finished with something else.
    """

    def setUp(self):
        self.notifier = support.Notifier()
        support.init_app_context(notifier=self.notifier)
        self.download = UpdateFileDownload()
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory)

    def _source(self, name, data):
        path = os.path.join(self.directory, name)
        with open(path, 'wb') as handle:
            handle.write(data)
        return path

    def _target(self):
        return os.path.join(self.directory, 'filmliste')

    def test_the_bar_moves_while_unpacking_bz2(self):
        source = self._source('filmliste.bz2', bz2.compress(_INCOMPRESSIBLE))
        self.download._decompress_bz2(source, self._target())
        self.assertGreater(len(self.notifier.progress), 1, 'the bar has to move')
        self.assertEqual(self.notifier.progress, sorted(self.notifier.progress))
        self.assertLess(self.notifier.progress[0], 100)
        self.assertLessEqual(max(self.notifier.progress), 100)

    def test_the_bar_moves_while_unpacking_gz(self):
        source = self._source('filmliste.gz', gzip.compress(_INCOMPRESSIBLE))
        self.download._decompress_gz(source, self._target())
        self.assertGreater(len(self.notifier.progress), 1, 'the bar has to move')
        self.assertEqual(self.notifier.progress, sorted(self.notifier.progress))
        self.assertLess(self.notifier.progress[0], 100)
        self.assertLessEqual(max(self.notifier.progress), 100)

    def test_unpacking_writes_what_was_packed(self):
        for (name, packer) in (('filmliste.bz2', bz2), ('filmliste.gz', gzip)):
            source = self._source(name, packer.compress(_PAYLOAD))
            unpack = (self.download._decompress_bz2 if packer is bz2
                      else self.download._decompress_gz)
            unpack(source, self._target())
            with open(self._target(), 'rb') as handle:
                self.assertEqual(handle.read(), _PAYLOAD, name)

    def test_the_number_is_only_reported_when_it_changes(self):
        source = self._source('filmliste.bz2', bz2.compress(_INCOMPRESSIBLE))
        self.download._decompress_bz2(source, self._target())
        self.assertEqual(len(self.notifier.progress),
                         len(set(self.notifier.progress)))

    def test_an_unknown_size_reports_nothing(self):
        self.download.shownPercent = -1
        self.download._reportUnpackProgress(1024, 0)
        self.assertEqual(self.notifier.progress, [])

    def test_the_dialog_is_told_that_unpacking_started(self):
        source = self._source('filmliste.bz2', bz2.compress(_PAYLOAD))
        self.download._decompress(source, self._target())
        self.assertIn('unpack', self.notifier.headings)

    def test_it_says_where_the_update_came_from(self):
        # Not the name on disk: that is the download's own scratch file,
        # tmp_filmliste-v3.db.bz2, which means nothing to anybody.
        source = self._source('tmp_filmliste-v3.db.bz2', bz2.compress(_PAYLOAD))
        url = 'https://liste.mediathekview.de/filmliste-v3.db.bz2'
        self.download._decompress(source, self._target(), url)
        self.assertEqual(self.notifier.messages, [url])


if __name__ == '__main__':
    unittest.main()
