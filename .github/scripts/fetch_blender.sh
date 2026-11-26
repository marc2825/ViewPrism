#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 marc2825
# SPDX-License-Identifier: GPL-3.0-or-later
# CI helper: resolve / download an official Blender Linux build and verify its SHA-256.
#   fetch_blender.sh resolve <series>          -> prints the latest patch version, e.g. 4.5.3
#   fetch_blender.sh fetch <version> <dest>    -> extracts to <dest>, prints the blender executable path
# Development/CI tooling only: the add-on itself never downloads anything.
set -euo pipefail

BASE="https://download.blender.org/release"
cmd="${1:?resolve|fetch}"

if [[ "$cmd" == "resolve" ]]; then
  series="${2:?series, e.g. 4.5}"
  listing="$(curl -fsSL --retry 3 "$BASE/Blender${series}/")"
  version="$(grep -oE "blender-${series//./\\.}\.[0-9]+-linux-x64\.tar\.xz" <<<"$listing" \
             | sed -E 's/^blender-([0-9.]+)-linux-x64\.tar\.xz$/\1/' | sort -uV | tail -n1)"
  if [[ -z "$version" ]]; then
    echo "no Linux x64 build found for Blender ${series}" >&2
    exit 1
  fi
  echo "$version"
  exit 0
fi

if [[ "$cmd" == "fetch" ]]; then
  version="${2:?version}"
  dest="${3:?destination}"
  series="${version%.*}"
  file="blender-${version}-linux-x64.tar.xz"
  mkdir -p "$dest"
  if [[ ! -x "$dest/blender-${version}-linux-x64/blender" ]]; then
    tmp="$(mktemp -d)"
    curl -fsSL --retry 3 -o "$tmp/$file" "$BASE/Blender${series}/$file"
    curl -fsSL --retry 3 -o "$tmp/sums.sha256" "$BASE/Blender${series}/blender-${version}.sha256"
    expected="$(grep -E "[[:space:]]\*?${file}\$" "$tmp/sums.sha256" | awk '{print $1}')"
    actual="$(sha256sum "$tmp/$file" | awk '{print $1}')"
    if [[ -z "$expected" || "$expected" != "$actual" ]]; then
      echo "SHA-256 mismatch for $file (expected '$expected', got '$actual')" >&2
      exit 1
    fi
    tar -xJf "$tmp/$file" -C "$dest"
    rm -rf "$tmp"
  fi
  echo "$dest/blender-${version}-linux-x64/blender"
  exit 0
fi

echo "unknown command $cmd" >&2
exit 2
