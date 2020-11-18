#!/usr/bin/env python3
#
# TODO this should be implemented as an fdroid plugin

import glob
import json
import os
import re
import sys
import yaml
from datetime import datetime
from fdroidserver import common, index, metadata, mirror, net, update
from urllib.parse import urlsplit, urlunsplit


class Options:
    allow_disabled_algorithms = False
    clean = False
    delete_unknown = True
    identity_file = None
    no_checksum = False
    no_keep_git_mirror_archive = False
    nosign = True
    pretty = False
    rename_apks = False
    verbose = True


def download_graphics(repourl, app):
    baseurl = urlsplit(repourl)
    for locale, entries in app.get('localized', {}).items():
        for k, v in entries.items():
            dirpath = None
            dlurl = None
            if k in ('icon', 'featureGraphic'):
                dirpath = os.path.join(app['packageName'], locale, k + v[v.rindex('.'):])
                dlpath = os.path.join('metadata', dirpath)
                dlurl = urlunsplit([baseurl.scheme,
                                    baseurl.netloc,
                                    os.path.join(baseurl.path, dirpath),
                                    None,
                                    None])
                if not os.path.exists(dlpath):
                    print('Downloading', dlurl)
                    os.makedirs(os.path.dirname(dlpath), exist_ok=True)
                    net.download_file(dlurl, dlpath)
            elif k.endswith('Screenshots'):
                for f in v:
                    dirpath = os.path.join(app['packageName'], locale, k, f)
                    dlpath = os.path.join('repo', dirpath)
                    dlurl = urlunsplit([baseurl.scheme,
                                        baseurl.netloc,
                                        os.path.join(baseurl.path, dirpath),
                                        None,
                                        None])
                    if not os.path.exists(dlpath):
                        print('Downloading', dlurl)
                        os.makedirs(os.path.dirname(dlpath), exist_ok=True)
                        net.download_file(dlurl, dlpath)
            elif k in ('summary', 'description'):
                f = os.path.join('metadata', app['packageName'], locale, k + '.txt')
                os.makedirs(os.path.dirname(f), exist_ok=True)
                with open(f, 'w') as fp:
                    fp.write(v)
            elif k == 'whatsNew':
                f = os.path.join('metadata', app['packageName'], locale, 'changelogs',
                                 '{}.txt'.format(app['suggestedVersionCode']))
                os.makedirs(os.path.dirname(f), exist_ok=True)
                with open(f, 'w') as fp:
                    fp.write(v)


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

obf_pat = re.compile(r'metadata/[0-9a-f]{64}\.yml')
for f in glob.glob(os.path.join('metadata', '*.yml')):
    if obf_pat.match(f):
        os.remove(f)
for f in glob.glob(os.path.join('repo', '*.obf.zip')):
    print('Creating metadata for OBF file:', f)
    data = {
        'AuthorName': 'OsmAnd',
        'WebSite': 'https://osmand.net',
        'Name': os.path.basename(f),
        'Summary': os.path.basename(f)[:-8].replace('_', ' ') + ' offline map for OsmAnd',
        'Description': (
            'This file can be downloaded and installed into OsmAnd to provide offline '
            'maps for the region described in the file name.  '
            'https://f-droid.org/packages/net.osmand.plus'
        ),
        'Categories': [
            'Offline',
            'OsmAnd',
        ],
    }
    with open(os.path.join('metadata', update.sha256sum(f) + '.yml'), 'w') as fp:
        yaml.dump(data, fp)

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
                    if k == 'added':
                        newapp[k] = datetime.fromtimestamp(int(v) / 1000)
                    else:
                        newapp[k[0].upper() + k[1:]] = v
                for k, v in from_metadata.items():
                    if not newapp.get(k):
                        newapp[k] = v
                newapp['Categories'] = newapp.get('Categories', []) + ['Offline']
                categories.update(newapp['Categories'])
                apps[app_id] = metadata.App(newapp)

                baseurl = urlsplit(url)
                i = 0
                for package in data['packages'].get(app_id):
                    urls.append(urlunsplit([baseurl.scheme,
                                            baseurl.netloc,
                                            os.path.join(baseurl.path, package['apkName']),
                                            None,
                                            None]))
                    i += 1
                    if i >= update.config['archive_older']:
                        break
                download_graphics(url, app)
                found = True
                break
        if found:
            break

mirror._run_wget(os.path.join(basedir, 'repo'), urls)
os.chdir(basedir)

knownapks = common.KnownApks()
apkcache = update.get_cache()
apks, cache_changed = update.process_apks(apkcache, REPO_DIR, knownapks)
files, file_cache_changed = update.scan_repo_files(apkcache, REPO_DIR, knownapks)
if cache_changed or file_cache_changed:
    update.write_cache(apkcache)

allrepofiles = apks + files
update.read_added_date_from_all_apks(apps, allrepofiles)
update.archive_old_apks(apps, allrepofiles, [], 'repo', 'archive', update.config['archive_older'])
repoapps = prepare_apps(apps, apks, repodirs[0])
index.make(repoapps, apks, REPO_DIR, False)
update.make_categories_txt(REPO_DIR, categories)
knownapks.writeifchanged()
