#!/bin/sh
# New versions only. Never edit an existing release or replace its assets.
set -eu
: "${VERSION:?Validated IPA version is required}"
: "${GITHUB_REPOSITORY:?Repository is required}"
: "${GITHUB_SHA:?Build commit is required}"
tag="v$VERSION"
if git ls-remote --exit-code --refs origin "refs/tags/$tag" > /dev/null; then
    echo "Release tag $tag already exists. Use a new version; nothing was published." >&2
    exit 1
else
    status=$?
    if [ "$status" -ne 2 ]; then
        echo "Could not check existing tags; refusing to publish." >&2
        exit "$status"
    fi
fi
# Creation fails on an existing release; no update/upload --clobber fallback.
gh release create "$tag" upload/KorSign.ipa \
    --repo "$GITHUB_REPOSITORY" --target "$GITHUB_SHA" \
    --title "KorSign $tag" --generate-notes
