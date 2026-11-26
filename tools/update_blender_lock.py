# SPDX-FileCopyrightText: 2026 marc2825
# SPDX-License-Identifier: GPL-3.0-or-later
"""Check or update ci/blender.lock against download.blender.org.

    python tools/update_blender_lock.py            # report newer patch releases (exit 1 if any)
    python tools/update_blender_lock.py --write    # pin the newest patch of each series + its SHA-256

For every <series> <platform> in the lock file the newest published patch version is looked up and
its SHA-256 is read from the official blender-<version>.sha256 list. Development/CI tooling only.
"""
import argparse
import re
import sys
import time
import urllib.request
from pathlib import Path

LOCK = Path(__file__).resolve().parent.parent / 'ci' / 'blender.lock'
BASE = 'https://download.blender.org/release'
SUFFIX = {'linux-x64': 'linux-x64.tar.xz', 'windows-x64': 'windows-x64.zip', 'macos-arm64': 'macos-arm64.dmg'}
HEADERS = {'User-Agent': 'ViewPrism-CI (+https://github.com/marc2825/ViewPrism)'}


def get(url, tries=5):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=60) as r:
                return r.read().decode('utf-8', 'replace')
        except OSError:
            if i == tries - 1:
                raise
            time.sleep(2 ** i * 5)


def read_lock():
    rows = []
    for line in LOCK.read_text(encoding='utf-8').splitlines():
        if line.strip() and not line.startswith('#'):
            series, version, platform, sha = line.split()
            rows.append(dict(series=series, version=version, platform=platform, sha=sha))
    return rows


def latest(series, platform):
    listing = get(f'{BASE}/Blender{series}/')
    found = re.findall(rf'blender-({re.escape(series)}\.\d+)-{re.escape(SUFFIX[platform])}', listing)
    if not found:
        raise SystemExit(f'no {platform} build listed for Blender {series}')
    return max(set(found), key=lambda v: tuple(int(x) for x in v.split('.')))


def official_sha(version, platform):
    series = version.rsplit('.', 1)[0]
    name = f'blender-{version}-{SUFFIX[platform]}'
    for line in get(f'{BASE}/Blender{series}/blender-{version}.sha256').splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip('*') == name:
            return parts[0]
    raise SystemExit(f'no checksum published for {name}')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--write', action='store_true', help='rewrite ci/blender.lock with the newest patch versions')
    a = ap.parse_args(argv)
    rows = read_lock()
    drift = []
    for r in rows:
        new = latest(r['series'], r['platform'])
        status = 'up to date' if new == r['version'] else f'newer: {new}'
        print(f"{r['series']:4s} {r['platform']:12s} locked {r['version']:8s} {status}")
        if new != r['version']:
            drift.append((r, new))
    if a.write:
        for r, new in drift:
            r['version'], r['sha'] = new, official_sha(new, r['platform'])
        header = [line for line in LOCK.read_text(encoding='utf-8').splitlines() if line.startswith('#')]
        body = [f"{r['series']} {r['version']:6s} {r['platform']:11s} {r['sha']}" for r in rows]
        LOCK.write_text('\n'.join(header + body) + '\n', encoding='utf-8', newline='\n')
        print(f'wrote {LOCK.name} ({len(drift)} update(s))')
        return 0
    return 1 if drift else 0


if __name__ == '__main__':
    sys.exit(main())
