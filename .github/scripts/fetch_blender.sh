#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 marc2825
# SPDX-License-Identifier: GPL-3.0-or-later
# CI helper: install an official Blender build and verify its SHA-256.
#   fetch_blender.sh lookup <series> [platform]
#       -> prints the version pinned in ci/blender.lock (no network)
#   fetch_blender.sh resolve <series> [platform]
#       -> prints the latest published patch version (network; only for the manual macOS probe)
#   fetch_blender.sh fetch <version> <archive_cache_dir> <install_dir> [platform]
#       -> downloads (or reuses) the archive, verifies it, extracts it, prints the executable path
# platform: linux-x64 (default) | windows-x64 | macos-arm64
#
# The expected SHA-256 comes from ci/blender.lock (reviewed, in the repository). Only versions that
# are not in the lock file fall back to the official checksum list. A cached archive is verified
# before every extraction; a mismatching one is deleted. With a cache hit and a locked version no
# request goes to download.blender.org (it rate-limits bursts of CI requests with HTTP 403).
# Development/CI tooling only: the add-on itself never downloads anything.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCK="$HERE/../../ci/blender.lock"
BASE="https://download.blender.org/release"
CURL=(curl -fsSL --retry 6 --retry-all-errors -A "ViewPrism-CI (+https://github.com/marc2825/ViewPrism)")
cmd="${1:?lookup|resolve|fetch}"

suffix() {
  case "$1" in
    linux-x64) echo "linux-x64.tar.xz" ;;
    windows-x64) echo "windows-x64.zip" ;;
    macos-arm64) echo "macos-arm64.dmg" ;;
    *) echo "unknown platform $1" >&2; exit 2 ;;
  esac
}

lock_field() {  # <match column> <value> <platform> <output column>
  awk -v c="$1" -v v="$2" -v p="$3" -v o="$4" '!/^#/ && NF >= 4 && $c == v && $3 == p {print $o; exit}' "$LOCK"
}

if [[ "$cmd" == "lookup" ]]; then
  series="${2:?series, e.g. 4.5}"
  platform="${3:-linux-x64}"
  version="$(lock_field 1 "$series" "$platform" 2)"
  [[ -n "$version" ]] || { echo "Blender ${series} ${platform} is not in ci/blender.lock" >&2; exit 1; }
  echo "$version"
  exit 0
fi

if [[ "$cmd" == "resolve" ]]; then
  series="${2:?series, e.g. 4.5}"
  sfx="$(suffix "${3:-linux-x64}")"
  listing="$("${CURL[@]}" "$BASE/Blender${series}/")"
  version="$(grep -oE "blender-${series//./\\.}\.[0-9]+-${sfx//./\\.}" <<<"$listing" \
             | sed -E 's/^blender-([0-9]+\.[0-9]+\.[0-9]+)-.*/\1/' | sort -uV | tail -n1)"
  [[ -n "$version" ]] || { echo "no ${sfx} build found for Blender ${series}" >&2; exit 1; }
  echo "$version"
  exit 0
fi

if [[ "$cmd" == "fetch" ]]; then
  version="${2:?version}"
  cache="${3:?archive cache dir}"
  install="${4:?install dir}"
  platform="${5:-linux-x64}"
  series="${version%.*}"
  file="blender-${version}-$(suffix "$platform")"
  mkdir -p "$cache" "$install"
  expected="$(lock_field 2 "$version" "$platform" 4)"
  if [[ -n "$expected" ]]; then
    echo "expected SHA-256 from ci/blender.lock" >&2
  else
    sums="$(mktemp)"
    "${CURL[@]}" -o "$sums" "$BASE/Blender${series}/blender-${version}.sha256"
    expected="$(grep -E "[[:space:]]\*?${file}\$" "$sums" | awk '{print $1}')"
    rm -f "$sums"
    [[ -n "$expected" ]] || { echo "no checksum published for $file" >&2; exit 1; }
    echo "expected SHA-256 from the official list (version not locked)" >&2
  fi
  if [[ -f "$cache/$file" ]] && [[ "$(sha256sum "$cache/$file" | awk '{print $1}')" != "$expected" ]]; then
    echo "cached $file does not match the expected SHA-256; discarding it" >&2
    rm -f "$cache/$file"
  fi
  if [[ ! -f "$cache/$file" ]]; then
    "${CURL[@]}" -o "$cache/$file.part" "$BASE/Blender${series}/$file"
    mv "$cache/$file.part" "$cache/$file"
  fi
  actual="$(sha256sum "$cache/$file" | awk '{print $1}')"
  if [[ "$expected" != "$actual" ]]; then
    echo "SHA-256 mismatch for $file (expected '$expected', got '$actual')" >&2
    rm -f "$cache/$file"
    exit 1
  fi
  echo "verified $file sha256=$actual" >&2
  case "$platform" in
    linux-x64)
      tar -xJf "$cache/$file" -C "$install"
      echo "$install/blender-${version}-linux-x64/blender" ;;
    windows-x64)
      python -I -c "import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" \
        "$cache/$file" "$install"
      echo "$install/blender-${version}-windows-x64/blender.exe" ;;
    macos-arm64)
      mnt="$(mktemp -d)"
      hdiutil attach -nobrowse -readonly -mountpoint "$mnt" "$cache/$file" > /dev/null
      cp -R "$mnt/Blender.app" "$install/"
      hdiutil detach "$mnt" > /dev/null
      echo "$install/Blender.app/Contents/MacOS/Blender" ;;
  esac
  exit 0
fi

echo "unknown command $cmd" >&2
exit 2
