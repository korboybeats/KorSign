#!/bin/sh
# Refresh the source feed from this fork's published release, then review/commit it.
set -eu
release=$(mktemp)
output=$(mktemp)
trap 'rm -f "$release" "$output"' EXIT HUP INT TERM
curl --fail --silent --show-error 'https://api.github.com/repos/korboybeats/KorSign/releases/latest' > "$release"
jq --slurpfile releases "$release" '
  $releases[0] as $release |
  if ($release.draft or ($release.tag_name | test("^v[0-9]+(\\.[0-9]+){1,3}$") | not))
  then error("Invalid release") else . end |
  .apps |= map(
    (if .bundleIdentifier == "com.korboy.korsign" then "KorSign.ipa"
     elif .bundleIdentifier == "com.korboy.korsign.dev" then "KorSign-Dev.ipa"
     else error("Unknown bundle identifier") end) as $name |
    ([$release.assets[] | select(.name == $name)][0] // error("Missing matching IPA")) as $asset |
    .version = ($release.tag_name | ltrimstr("v")) |
    .versionDate = $release.published_at |
    .size = $asset.size |
    .downloadURL = $asset.browser_download_url |
    .versions = [{version: .version, date: .versionDate, size: .size, downloadURL: .downloadURL}]
  )' app-repo.json > "$output"
mv "$output" app-repo.json
