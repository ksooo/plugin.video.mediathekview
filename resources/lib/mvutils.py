# -*- coding: utf-8 -*-
"""
Utilities module

Copyright (c) 2017-2019, Leo Moll
SPDX-License-Identifier: MIT
"""

import os
import re
import sys
import stat
import string
import json
import datetime
from contextlib import closing
from codecs import open
from functools import reduce

from urllib.parse import urlencode
from urllib.request import urlopen

from contextlib import closing
from resources.lib.exceptions import ExitRequested

# -- Kodi Specific Imports ----------------------------------
try:
    import xbmcvfs
    IS_KODI = True
except ImportError:
    IS_KODI = False


def coalesce(*arg):
  return reduce(lambda x, y: x if x is not None else y, arg)


def unixtimestamp2iso(uxtimestamp):
    return datetime.datetime.fromtimestamp(uxtimestamp).strftime('%Y-%m-%d %H:%M:%S')

def dir_exists(name):
    """
    Tests if a directory exists

    Args:
        name(str): full pathname of the directory
    """
    try:
        state = os.stat(name)
        return stat.S_ISDIR(state.st_mode)
    except OSError:
        return False


def file_exists(name):
    """
    Tests if a file exists

    Args:
        name(str): full pathname of the file
    """
    try:
        state = os.stat(name)
        return stat.S_ISREG(state.st_mode)
    except OSError:
        return False


def file_size(name):
    """
    Get the size of a file

    Args:
        name(str): full pathname of the file
    """
    try:
        state = os.stat(name)
        return state.st_size
    except OSError:
        return 0


def file_remove(name):
    """
    Delete a file

    Args:
        name(str): full pathname of the file
    """
    if file_exists(name):
        try:
            os.remove(name)
            return True
        except OSError:
            pass
    return False


def file_rename(srcname, dstname):
    """
    Rename a file

    Args:
        srcname(str): name of the source file
        dstname(str): name of the file after the rename operation
    """
    if file_exists(srcname):
        try:
            os.rename(srcname, dstname)
            return True
        except OSError:
            # maybe windows on overwrite. try non atomic rename
            try:
                os.remove(dstname)
                os.rename(srcname, dstname)
                return True
            except OSError:
                return False
    return False


def make_search_string(val):
    """
    Reduces a string to a simplified representation
    containing only a well defined set of characters
    for a simplified search
    """
    cset = string.ascii_letters + string.digits + ' _-#'
    search = ''.join([c for c in val if c in cset])
    return search.upper().strip()


def make_duration(val):
    """
    Converts a string in `hh:mm:ss` representation
    to the equivalent number of seconds

    Args:
        val(str): input string in format `hh:mm:ss`
    """
    if val == "00:00:00":
        return 0
    elif val is None:
        return 0
    parts = val.split(':')
    if len(parts) != 3:
        return 0
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])


def cleanup_filename(val):
    """
    Strips strange characters from a string in order
    to create a valid filename

    Args:
        val(str): input string
    """
    cset = string.ascii_letters + string.digits + \
        u' _-#äöüÄÖÜßáàâéèêíìîóòôúùûÁÀÉÈÍÌÓÒÚÙçÇœ'
    search = ''.join([c for c in val if c in cset])
    return search.strip()


def url_retrieve(url, filename, reporthook, chunk_size=65536, aborthook=None):
    """
    Copy a network object denoted by a URL to a local file

    Args:
        url(str): the source url of the object to retrieve

        filename(str): the destination filename

        reporthook(function): a hook function that will be called once on
            establishment of the network connection and once after each
            block read thereafter. The hook will be passed three arguments;
            a count of blocks transferred so far, a block size in bytes,
            and the total size of the file.

        chunk_size(int, optional): size of the chunks read by the function.
            Default is 8192

        aborthook(function, optional): a hook function that will be called
            once on establishment of the network connection and once after
            each block read thereafter. If specified the operation will be
            aborted if the hook function returns `True`
    """
    with closing(urlopen(url, timeout=10)) as src, closing(open(filename, 'wb')) as dst:
        _chunked_url_copier(src, dst, reporthook, chunk_size, aborthook)


def url_retrieve_vfs(url, filename, reporthook, chunk_size=65536, aborthook=None):
    """
    Copy a network object denoted by a URL to a local file using
    Kodi's VFS functions

    Args:
        url(str): the source url of the object to retrieve

        filename(str): the destination filename

        reporthook(function): a hook function that will be called once on
            establishment of the network connection and once after each
            block read thereafter. The hook will be passed three arguments;
            a count of blocks transferred so far, a block size in bytes,
            and the total size of the file.

        chunk_size(int, optional): size of the chunks read by the function.
            Default is 8192

        aborthook(function, optional): a hook function that will be called
            once on establishment of the network connection and once after
            each block read thereafter. If specified the operation will be
            aborted if the hook function returns `True`
    """
    with closing(urlopen(url, timeout=10)) as src, closing(xbmcvfs.File(filename, 'wb')) as dst:
        _chunked_url_copier(src, dst, reporthook, chunk_size, aborthook)


# TODO: Review if it can be merged with kodiaddon.build_url
def build_url(query):
    """
    Builds a valid plugin url based on the supplied query object

    Args:
        query(object): a query object
    """
    return sys.argv[0] + '?' + urlencode(query)


def _chunked_url_copier(src, dst, reporthook, chunk_size, aborthook):
    aborthook = aborthook if aborthook is not None else lambda: False
    total_size = int(
        src.info().get('Content-Length').strip()
    ) if src.info() and src.info().get('Content-Length') else 0
    total_chunks = 0

    while not aborthook():
        reporthook(total_chunks, chunk_size, total_size)
        byteStringchunk = src.read(chunk_size)
        if not byteStringchunk:
            # operation has finished
            return
        dst.write(bytearray(byteStringchunk))
        total_chunks += 1
    # abort requested
    raise ExitRequested('Reception interrupted.')

def readTextFile( pFilename, pEncoding='utf-8'):
    """
    Read a file into a string

    Args:
        pFilename(str): the source file to read

        encoding(str): the destination filename

    """
    with closing(open(pFilename, 'r', encoding=pEncoding)) as txtFile:
        data = txtFile.read()
    return data

def writeTextFile( pFilename, pText, pEncoding='utf-8'):
    """
    Read a file into a string

    Args:
        pFilename(str): the target file to write to

        pText(str): txt data
        
        encoding(str): Encoding by default utf-8

    """
    with closing(open(pFilename, 'w', encoding=pEncoding)) as txtFile:
        data = txtFile.write(pText)
    

def loadJsonFile(filename):
    #
    data = None
    # try:
    with closing(open(filename, encoding='utf-8')) as json_file:
        data = json.load(json_file)
    # pylint: disable=broad-except
    # except Exception as err:
    #    pass
    return data


def saveJsonFile(filename, pData):
    #
    try:
        with closing(open(filename, 'w', encoding='utf-8')) as json_file:
            json.dump(pData, json_file)
    # pylint: disable=broad-except
    except Exception as err:
        return False
    #
    return True

