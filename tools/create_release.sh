#!/bin/sh
# New versions only. Never edit an existing release or replace its assets.
set -eu
: "${VERSION:?Validated IPA version is required}"
: "${GITHUB_REPOSITORY:?Repository is required}"
: "${GITHUB_SHA:?Build commit is required}"
revision="${REVISION:-}"
tag="v$VERSION"
if [ -n "$revision" ]; then
    case "$revision" in *[!0-9]*|0) echo "Invalid revision" >&2; exit 1;; esac
    tag="$tag-r$revision"
fi
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
set --
if [ "${DRAFT:-false}" = true ]; then set -- "$@" --draft; fi
if [ -n "${NOTES_FILE:-}" ]; then
    set -- "$@" --notes-file "$NOTES_FILE"
else
    set -- "$@" --generate-notes
fi
gh release create "$tag" upload/KorSign.ipa \
    --repo "$GITHUB_REPOSITORY" --target "$GITHUB_SHA" \
    --title "${RELEASE_TITLE:-KorSign $tag}" "$@"
