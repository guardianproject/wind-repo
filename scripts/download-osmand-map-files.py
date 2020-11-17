#!/usr/bin/env python3
#
# https://download.osmand.net/list.php

import os
import requests
import shutil
import sys
import time
from clint.textui import progress
from email.utils import parsedate_to_datetime
from fdroidserver import update

HEADERS = {'User-Agent': 'F-Droid'}


def http_get(url, local_filepath, timeout=600):
    """
    Downloads the content from the given URL by making a GET request.

    :param url: The URL to download from.
    """
    etag = None
    local_filepath = os.path.relpath(local_filepath)
    if os.path.exists(local_filepath):
        mtime = os.path.getmtime(local_filepath)
        size = os.path.getsize(local_filepath)
        etag = ('"%x-%x"' % (int(mtime), size))
        
    if etag:
        r = requests.head(url, allow_redirects=True,
                          headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        if 'ETag' in r.headers and etag == r.headers['ETag']:
            print(local_filepath, 'is current (%s)' % etag)
            return
        print('Downloading', local_filepath, etag, r.headers['ETag'])
    else:
        print('Downloading', local_filepath, etag, None)

    # the stream=True parameter keeps memory usage low
    r = requests.get(url, stream=True, allow_redirects=True,
                     headers=HEADERS, timeout=timeout)
    r.raise_for_status()

    last_modified = int(parsedate_to_datetime(r.headers['Last-Modified']).timestamp())
    content_length = r.headers['Content-Length']
    with open(local_filepath, 'wb') as f:
        for chunk in progress.bar(r.iter_content(chunk_size=8192),
                                  expected_size=(int(content_length) / 8192) + 1):
            if chunk:  # filter out keep-alive new chunks
                f.write(chunk)
                f.flush()
    print()
    os.utime(local_filepath, times=(int(time.time()), last_modified))


basedir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(basedir)
tmpdir = os.path.join(basedir, 'tmp')
cache_file = os.path.join(tmpdir, 'obfcache.json')
cache = None
if os.path.exists(cache_file):
    try:
        with open(cache_file) as fp:
            cache = json.load(fp)
        if sorted(files) == sorted(cache['etags'].keys()):
            print('Loading indexes from cache')
        else:
            print('Reseting cache')
            cache = None
    except Exception as e:
        print(e)
if not cache:
    cache = {'etags': dict()}


files = [
    'Puerto-rico_centralamerica_2.obf.zip',
    'Virgin-islands-british_centralamerica_2.obf.zip',
    'Virgin-islands-us_centralamerica_2.obf.zip',
]
baseurl = 'https://download.osmand.net/download?standard=yes&file='

for f in files:
    url = baseurl + f
    print('\n---------------------------------------------------')
    print(url)
    local_filepath = os.path.join(basedir, 'repo', f)
    http_get(url, local_filepath)
    sha256 = update.sha256sum(local_filepath)
    icon = os.path.join('metadata', sha256, 'en-US', 'icon.png')
    if not os.path.exists(icon):
        os.makedirs(os.path.dirname(icon), exist_ok=True)
        shutil.copy('graphics/%s.png' % f, icon)
