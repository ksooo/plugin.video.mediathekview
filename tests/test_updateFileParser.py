# -*- coding: utf-8 -*-
"""
Tests for the buffered reader that splits the downloaded film list

SPDX-License-Identifier: MIT
"""

import os
import shutil
import tempfile
import unittest

from tests import support

from resources.lib.updateFileParser import UpdateFileParser


class UpdateFileParserTest(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.logger = support.Logger()

    def tearDown(self):
        shutil.rmtree(self.directory)

    def _parser(self, content, buffer_size):
        filename = os.path.join(self.directory, 'filmlist')
        with open(filename, 'w', encoding='utf-8') as handle:
            handle.write(content)
        parser = UpdateFileParser(self.logger, buffer_size, filename)
        parser.init()
        return parser

    def _read_all(self, parser, separator):
        parts = []
        while True:
            part = parser.next(separator)
            if part == '':
                return parts
            parts.append(part)

    def test_splits_on_the_separator(self):
        parser = self._parser('alpha|beta|gamma', 1024)
        self.assertEqual(self._read_all(parser, '|'), ['alpha', 'beta', 'gamma'])
        parser.close()

    def test_splits_across_buffer_refills(self):
        # The film list is far larger than the buffer, so every separator is
        # found only after a refill. A buffer shorter than the parts forces
        # that path for each of them.
        parser = self._parser('alpha|beta|gamma', 4)
        self.assertEqual(self._read_all(parser, '|'), ['alpha', 'beta', 'gamma'])
        parser.close()

    def test_separator_longer_than_one_character(self):
        parser = self._parser('"alpha","beta"', 4)
        self.assertEqual(parser.next('","'), '"alpha')
        self.assertEqual(parser.next('","'), 'beta"')
        parser.close()

    def test_reports_end_of_file_as_empty_string(self):
        parser = self._parser('alpha', 1024)
        self.assertEqual(parser.next('|'), 'alpha')
        self.assertEqual(parser.next('|'), '')
        self.assertEqual(parser.next('|'), '')
        parser.close()


if __name__ == '__main__':
    unittest.main()
