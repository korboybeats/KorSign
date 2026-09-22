# ZIPFoundation

Vendored from https://github.com/weichsel/ZIPFoundation at `22787ffb59de99e5dc1fbfe80b19c97a904ad48d` under the
included MIT license. KorSign adds an opt-in system-zlib DEFLATE decoder for IPA
imports. The default decoder and archive writing remain unchanged. Local changes
are in Archive+Reading.swift, Archive+Helpers.swift, Data+ZlibImport.swift, and
Entry.swift (preserving valid zero-valued ZIP64 fields).
File extraction accepts an optional throwing checkpoint before each output chunk
so callers can cooperatively pause or cancel without closing a live archive.
The package manifest targets Apple platforms used by KorSign.

Run `python3 tests/test_archive_extraction.py --checkouts <cached-checkouts>`
to verify archive boundaries and the import decoder.

## Maintaining the local changes

`UPSTREAM_REVISION` records the source revision. Preserve the upstream license and
source notices. When updating, review the decoder hook in both extraction overloads,
its propagation through `readCompressed`, and `Data+ZlibImport.swift`. Keep system
zlib opt-in and archive writing unchanged. Keep the privacy manifest bundled and
the ZIPFoundation entry in `license_plist.yml`.

The import decoder uses bounded input/output chunks, checks declared input and
output lengths, and rejects incomplete or trailing streams. The extraction caller
must compare the returned CRC with the archive checksum. Archive handles are not
shared across simultaneous imports. Run archive, import-cleanup, import-lifecycle,
import-control synchronization, and download-ownership tests before updating this
copy. Synthetic ZIP64 fixtures exercise format handling without allocating multi-gigabyte outputs.
