import Foundation
import zlib

extension Data {
    static func inflateImport(size: UInt64, expectedSize: UInt64, bufferSize: Int,
                              skipCRC32: Bool, provider: Provider, consumer: Consumer) throws -> CRC32 {
        guard bufferSize > 0, bufferSize <= Int(UInt32.max), size <= UInt64(Int64.max) else {
            throw Archive.ArchiveError.invalidEntrySize
        }
        var stream = z_stream()
        guard inflateInit2_(&stream, -MAX_WBITS, ZLIB_VERSION, Int32(MemoryLayout<z_stream>.size)) == Z_OK else {
            throw CocoaError(.fileReadCorruptFile)
        }
        defer { inflateEnd(&stream) }
        var position: UInt64 = 0
        var produced: UInt64 = 0
        var checksum: CRC32 = 0
        var ended = false
        while !ended {
            guard position < size else { throw CocoaError(.fileReadCorruptFile) }
            let count = Int(Swift.min(UInt64(bufferSize), size - position))
            var input = try provider(Int64(position), count)
            guard input.count == count else { throw CocoaError(.fileReadCorruptFile) }
            position += UInt64(input.count)
            try input.withUnsafeMutableBytes { raw in
                stream.next_in = raw.bindMemory(to: UInt8.self).baseAddress
                stream.avail_in = UInt32(raw.count)
                repeat {
                    let before = stream.avail_in
                    var output = Data(count: bufferSize)
                    let result = output.withUnsafeMutableBytes { target -> Int32 in
                        stream.next_out = target.bindMemory(to: UInt8.self).baseAddress
                        stream.avail_out = UInt32(target.count)
                        return inflate(&stream, Z_NO_FLUSH)
                    }
                    guard result == Z_OK || result == Z_STREAM_END || result == Z_BUF_ERROR else {
                        throw CocoaError(.fileReadCorruptFile)
                    }
                    output.count = bufferSize - Int(stream.avail_out)
                    guard UInt64(output.count) <= expectedSize - produced else { throw Archive.ArchiveError.invalidEntrySize }
                    produced += UInt64(output.count)
                    if !skipCRC32 { checksum = output.crc32(checksum: checksum) }
                    if !output.isEmpty { try consumer(output) }
                    if result == Z_STREAM_END {
                        guard stream.avail_in == 0, position == size, produced == expectedSize else {
                            throw CocoaError(.fileReadCorruptFile)
                        }
                        ended = true
                        break
                    }
                    if before == stream.avail_in && output.isEmpty {
                        guard stream.avail_in == 0 else { throw CocoaError(.fileReadCorruptFile) }
                        break
                    }
                } while stream.avail_in > 0 || stream.avail_out == 0
            }
        }
        return checksum
    }
}
