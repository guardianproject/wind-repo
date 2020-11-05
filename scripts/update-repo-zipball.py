#!/usr/bin/env python3

import os
import subprocess
import sys
import tempfile
import yaml
import zipfile
from urllib.parse import urlparse

# taken from fdroidserver/deploy.py
AUTO_S3CFG = '.fdroid-deploy-s3cfg'

basedir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tmpdir = tempfile.mkdtemp(prefix='.%s-' % os.path.basename(__file__))
zipball = os.path.join(tmpdir, 'repo.zip')
print(zipball)

with open(os.path.join(basedir, 'config.yml')) as fp:
    config = yaml.load(fp)
reponame = urlparse(config['repo_url']).netloc

paths = []
for root, dirs, files in os.walk(os.path.join(basedir, 'repo')):
    for f in files:
        paths.append(os.path.join(os.path.relpath(root), f))

try:
    with zipfile.ZipFile(zipball, 'w') as zip:
        for path in sorted(paths):
            zip.write(path, os.path.join(reponame, 'fdroid', path))

    s3cmd_config = os.path.join(basedir, AUTO_S3CFG)
    if not os.path.exists(s3cmd_config):
        print('ERROR: cannot find', AUTO_S3CFG)
        sys.exit(1)

    subprocess.run(
        [
            's3cmd',
            '--config=' + s3cmd_config,  # created by `fdroid deploy`
            'sync',
            '--acl-public',
            '--verbose',
            zipball,
            's3://%s/' % config['awsbucket'],
        ],
        check=True,
    )

finally:
    if os.path.exists(zipball):
        os.remove(zipball)
