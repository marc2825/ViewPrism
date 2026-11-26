# SPDX-FileCopyrightText: 2026 marc2825
# SPDX-License-Identifier: GPL-3.0-or-later
"""Scan files (or the whole git history) for private data and credentials.

    python tools/privacy_scan.py                 # tracked files in the working tree
    python tools/privacy_scan.py --history       # every blob reachable from any ref
    python tools/privacy_scan.py PATH [PATH...]  # specific files/directories

Detects e-mail addresses (any provider), user-home paths (Windows, macOS, Linux, WSL), common
credential formats and PNG text/EXIF metadata. Findings are reported with the matched value masked,
so running this in CI does not republish what it finds. Exit code 1 when anything is found.
"""
import argparse
import os
import re
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Each rule: (name, compiled regex). Literals are split so this file does not match itself.
RULES = [
    ('email address', re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}')),
    ('Windows user path', re.compile(r'[A-Za-z]:[\\/]{1,2}' + 'Users' + r'[\\/]{1,2}(?!<|Public\b|Default\b|runneradmin\b)[^\\/\s"\'<>*]+',
                                     re.I)),
    ('macOS user path', re.compile(r'/' + 'Users' + r'/(?!<|Shared\b|runner\b)[A-Za-z0-9._-]+')),
    ('Linux home path', re.compile(r'/' + 'home' + r'/(?!<|runner\b)[a-z_][a-z0-9_-]*')),
    ('WSL path', re.compile(r'\\\\wsl(?:\$|\.localhost)\\', re.I)),
    ('GitHub token', re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_' + r'pat_[A-Za-z0-9_]{20,})')),
    ('AWS access key', re.compile(r'\b(?:AKIA|ASIA)[0-9A-Z]{16}\b')),
    ('Google API key', re.compile(r'\bAIza[0-9A-Za-z_-]{35}\b')),
    ('Slack token', re.compile(r'\bxox[abprs]-[0-9A-Za-z-]{10,}')),
    ('private key', re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?' + 'PRIVATE KEY-----')),
    ('credential assignment', re.compile(r'(?i)\b(?:api[_-]?key|secret|passw(?:or)?d|token)\b\s*[:=]\s*["\'][^"\'\s]{12,}["\']')),
]
# Values that are known to be safe in this repository.
ALLOW = [
    re.compile(r'@users\.noreply\.github\.com$'),
    re.compile(r'^noreply@(?:github\.com|anthropic\.com)$'),
    re.compile(r'@example\.(?:com|org|net)$'),
    re.compile(r'^[\w.+-]+@[\w-]+\.(?:invalid|test)$'),
    re.compile(r'^git@github\.com$'),
]
TEXT_SUFFIXES = {'.py', '.md', '.txt', '.toml', '.yml', '.yaml', '.json', '.log', '.sh', '.cfg', '.ini',
                 '.html', '.svg', '.csv', ''}
SKIP_DIRS = {'.git', '__pycache__', 'dist', '.venv'}


def _mask(value):
    if len(value) <= 6:
        return '*' * len(value)
    return value[:3] + '*' * (len(value) - 5) + value[-2:]


def scan_text(text, name='<text>'):
    """Return findings for a text blob as human-readable strings with masked values."""
    findings = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for rule, rx in RULES:
            for m in rx.finditer(line):
                value = m.group(0)
                if rule == 'email address' and any(a.search(value) for a in ALLOW):
                    continue
                findings.append(f'{name}:{lineno}: {rule}: {_mask(value)}')
    return findings


def png_metadata(data, name='<png>'):
    """PNG text/EXIF chunks (tEXt, iTXt, zTXt, eXIf, tIME) that could carry personal metadata."""
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        return []
    findings, pos = [], 8
    while pos + 8 <= len(data):
        (length,) = struct.unpack('>I', data[pos:pos + 4])
        kind = data[pos + 4:pos + 8].decode('latin-1')
        if kind in ('tEXt', 'iTXt', 'zTXt', 'eXIf', 'tIME'):
            findings.append(f'{name}: PNG metadata chunk {kind} ({length} bytes)')
        if kind == 'IEND':
            break
        pos += 12 + length
    return findings


def strip_png_metadata(path):
    """Rewrite a PNG without text/EXIF/time chunks (pixels untouched). Returns removed chunk names."""
    data = Path(path).read_bytes()
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        return []
    out, removed, pos = [data[:8]], [], 8
    while pos + 8 <= len(data):
        (length,) = struct.unpack('>I', data[pos:pos + 4])
        kind = data[pos + 4:pos + 8].decode('latin-1')
        chunk = data[pos:pos + 12 + length]
        if kind in ('tEXt', 'iTXt', 'zTXt', 'eXIf', 'tIME'):
            removed.append(kind)
        else:
            out.append(chunk)
        pos += 12 + length
        if kind == 'IEND':
            break
    if removed:
        Path(path).write_bytes(b''.join(out))
    return removed


def scan_bytes(data, name):
    if name.lower().endswith('.png'):
        return png_metadata(data, name)
    if Path(name).suffix.lower() in TEXT_SUFFIXES or Path(name).name in ('LICENSE', 'CODEOWNERS'):
        return scan_text(data.decode('utf-8', errors='replace'), name)
    return []


def tracked_files():
    out = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, capture_output=True, check=True).stdout
    return [ROOT / p for p in out.decode('utf-8').split('\0') if p]


def walk(paths):
    for p in paths:
        p = Path(p)
        if p.is_dir():
            for sub in p.rglob('*'):
                if sub.is_file() and not (set(sub.parts) & SKIP_DIRS):
                    yield sub
        elif p.is_file():
            yield p


def history_blobs():
    """(path, bytes) for every blob reachable from any ref (each blob once)."""
    objs = subprocess.run(['git', 'rev-list', '--all', '--objects'], cwd=ROOT, capture_output=True,
                          check=True).stdout.decode('utf-8', errors='replace').splitlines()
    entries = [line.split(' ', 1) for line in objs if ' ' in line]
    proc = subprocess.Popen(['git', 'cat-file', '--batch'], cwd=ROOT, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE)
    for sha, path in entries:
        proc.stdin.write((sha + '\n').encode())
        proc.stdin.flush()
        header = proc.stdout.readline().split()
        if len(header) < 3:
            continue
        size = int(header[2])
        data = proc.stdout.read(size)
        proc.stdout.read(1)
        if header[1] == b'blob':
            yield path, data
    proc.stdin.close()
    proc.wait()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('paths', nargs='*')
    ap.add_argument('--history', action='store_true', help='scan every blob in the git history')
    ap.add_argument('--strip-png', action='store_true', help='remove text/EXIF/time chunks from the given PNGs')
    a = ap.parse_args(argv)
    if a.strip_png:
        for f in walk(a.paths):
            if f.suffix.lower() == '.png':
                removed = strip_png_metadata(f)
                if removed:
                    print(f'stripped {",".join(removed)} from {f}')
        return 0
    findings = []
    if a.history:
        for path, data in history_blobs():
            findings += scan_bytes(data, f'history:{path}')
    else:
        files = list(walk(a.paths)) if a.paths else tracked_files()
        for f in files:
            try:
                rel = os.path.relpath(f, ROOT)
            except ValueError:
                rel = str(f)
            findings += scan_bytes(Path(f).read_bytes(), rel.replace('\\', '/'))
    for f in findings:
        print(f)
    print(f'privacy scan: {len(findings)} finding(s)')
    return 1 if findings else 0


if __name__ == '__main__':
    sys.exit(main())
