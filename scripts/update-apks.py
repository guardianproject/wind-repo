#!/usr/bin/env python3
#

import glob
import json
import os
import sys
from fdroidserver import common, index, metadata, mirror, update
from urllib.parse import urlsplit, urlunsplit


class Options:
    allow_disabled_algorithms = False
    clean = False
    delete_unknown = False
    identity_file = None
    no_checksum = False
    no_keep_git_mirror_archive = False
    nosign = True
    pretty = False
    rename_apks = True
    verbose = True


REPO_DIR = 'repo'
update.config = common.read_config(Options)
update.options = Options
mirror.options = Options

# order by highest priority first
source_repos = [
    'https://briarproject.org/fdroid/repo?fingerprint=1FB874BEE7276D28ECB2C9B06E8A122EC4BCB4008161436CE474C257CBF49BD6',
    'https://guardianproject.info/fdroid/repo?fingerprint=B7C2EEFD8DAC7806AF67DFCD92EB18126BC08312A7F2D6F3862E46013C7A6135',
    'https://f-droid.org/repo?fingerprint=43238D512C1E5EB2D6569F4A3AFBF5523418B82E0A3ED1552770ABB9A9C9CCAB',
    'https://apt.izzysoft.de/fdroid/repo?fingerprint=3BF0D6ABFEAE2F401707B6D966BE743BF0EEE49C2561B9BA39073711F628937A',
]

basedir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(basedir)
tmpdir = os.path.join(basedir, 'tmp')
os.makedirs(tmpdir, exist_ok=True)
cache_file = os.path.join(tmpdir, os.path.basename(__file__) + '-cache.json')
cache = None
if os.path.exists(cache_file):
    try:
        with open(cache_file) as fp:
            cache = json.load(fp)
        if sorted(source_repos) == sorted(cache['etags'].keys()):
            print('Loading indexes from cache')
        else:
            print('Reseting cache')
            cache = None
    except Exception as e:
        print(e)
if not cache:
    cache = {'etags': {}, 'indexes': {}}

for url in source_repos:
    print(url)
    etags = cache['etags']
    data, etag = index.download_repo_index(url, etags.get(url))
    if data is None:
        data = cache['indexes'].get(url)
    cache['indexes'][url] = data
    if data is not None and etag != etags.get(url):
        etags[url] = etag
        with open(cache_file, 'w') as fp:
            json.dump(cache, fp, indent=2, sort_keys=True)

urls = []
categories = set()
find_repo = dict()
apps_from_repo = dict()
apps = metadata.read_metadata()

for app_id in apps.keys():
    found = False
    for url in source_repos:
        data = cache['indexes'][url]
        for app in data['apps']:
            if app_id == app['packageName']:
                from_metadata = apps[app_id]
                newapp = dict()
                for k, v in app.items():
                    # convert to field names used in metadata files
                    newapp[k[0].upper() + k[1:]] = v
                apps[app_id] = {**app, **from_metadata}
                apps[app_id]['Categories'] = apps[app_id].get('Categories', []) + ['Offline']
                categories.update(apps[app_id]['Categories'])
                baseurl = urlsplit(url)
                for package in data['packages'].get(app_id):
                    urls.append(urlunsplit([baseurl.scheme,
                                            baseurl.netloc,
                                            os.path.join(baseurl.path, package['apkName']),
                                            None,
                                            None]))
                # TODO download graphics
                found = True
                break
        if found:
            break

mirror._run_wget(os.path.join(basedir, 'repo'), urls)
os.chdir(basedir)

knownapks = common.KnownApks()
apkcache = update.get_cache()
apks, cache_changed = update.process_apks(apkcache, REPO_DIR, knownapks, True)
files, file_cache_changed = update.scan_repo_files(apkcache, REPO_DIR, knownapks, True)
if cache_changed or file_cache_changed:
    update.write_cache(apkcache)

update.apply_info_from_latest_apk(apps, apks)
index.make(apps, apks, REPO_DIR, False)
update.make_categories_txt(REPO_DIR, categories)
