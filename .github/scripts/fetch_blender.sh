#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 marc2825
# SPDX-License-Identifier: GPL-3.0-or-later
# CI helper: resolve / download an official Blender build and verify its SHA-256.
#   fetch_blender.sh resolve <series> [platform]
#       -> prints the latest patch version of a series, e.g. 4.5.17
#   fetch_blender.sh fetch <version> <archive_cache_dir> <install_dir> [platform]
#       -> downloads (or reuses) the archive, verifies it, extracts it, prints the executable path
# platform: linux-x64 (default) | windows-x64 | macos-arm64
#
# CI caches only the downloaded *archive*. The official checksum list is downloaded fresh on every
# run (never cached) and the archive is re-verified against it before extraction, so a stale or
# tampered cache entry is rejected and deleted instead of being executed.
# Development/CI tooling only: the add-on itself never downloads anything.
set -euo pipefail

BASE="https://download.blender.org/release"
cmd="${1:?resolve|fetch}"

suffix() {
  case "$1" in
    linux-x64) echo "linux-x64.tar.xz" ;;
    windows-x64) echo "windows-x64.zip" ;;
    macos-arm64) echo "macos-arm64.dmg" ;;
    *) echo "unknown platform $1" >&2; exit 2 ;;
  esac
}

if [[ "$cmd" == "resolve" ]]; then
  series="${2:?series, e.g. 4.5}"
  sfx="$(suffix "${3:-linux-x64}")"
  listing="$(curl -fsSL --retry 3 "$BASE/Blender${series}/")"
  version="$(grep -oE "blender-${series//./\\.}\.[0-9]+-${sfx//./\\.}" <<<"$listing" \
             | sed -E 's/^blender-([0-9]+\.[0-9]+\.[0-9]+)-.*/\1/' | sort -uV | tail -n1)"
  if [[ -z "$version" ]]; then
    echo "no ${sfx} build found for Blender ${series}" >&2
    exit 1
  fi
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
  sums="$(mktemp)"
  curl -fsSL --retry 3 -o "$sums" "$BASE/Blender${series}/blender-${version}.sha256"
  expected="$(grep -E "[[:space:]]\*?${file}\$" "$sums" | awk '{print $1}')"
  rm -f "$sums"
  if [[ -z "$expected" ]]; then
    echo "no checksum published for $file" >&2
    exit 1
  fi
  if [[ -f "$cache/$file" ]] && [[ "$(sha256sum "$cache/$file" | awk '{print $1}')" != "$expected" ]]; then
    echo "cached $file does not match the official SHA-256; discarding it" >&2
    rm -f "$cache/$file"
  fi
  if [[ ! -f "$cache/$file" ]]; then
    curl -fsSL --retry 3 -o "$cache/$file.part" "$BASE/Blender${series}/$file"
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
