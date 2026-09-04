//
//  SwiftAR.swift
//  SwiftAR
//
//  Created by nekohaxx on 8/18/24.
//

import Foundation

class AR: NSObject {
	private var _data: Data
	
	init(with url: URL) throws {
		self._data = try Data(contentsOf: url)
		super.init()
	}
	
	func extract() async throws -> [ARFileModel] {
		guard _data.starts(with: Data("!<arch>\n".utf8)) else {
			throw ARError.badArchive("Invalid magic")
		}
		var offset = 8
		var files: [ARFileModel] = []
		while offset < _data.count {
			let file = try _getFileInfo(_data, offset)
			files.append(file)
			// The header and payload extents were checked before either addition.
			offset += 60 + file.size
			if file.size % 2 != 0 {
				guard offset < _data.count, _data[offset] == 0x0a else {
					throw ARError.badArchive("Missing member padding")
				}
				offset += 1
			}
		}
		// Validate all member names before callers write any of their contents.
		for file in files { try ArchiveExtraction.validatePath(file.name) }
		return files
	}

	private func _getFileInfo(_ data: Data, _ offset: Int) throws -> ARFileModel {
		guard offset <= data.count, data.count - offset >= 60 else {
			throw ARError.badArchive("Truncated member header")
		}
		guard data[offset + 58] == 0x60, data[offset + 59] == 0x0a else {
			throw ARError.badArchive("Invalid member header")
		}
		func field(_ start: Int, _ length: Int) throws -> String {
			guard let value = String(data: data.subdata(in: offset + start..<offset + start + length), encoding: .ascii) else {
				throw ARError.badArchive("Non-ASCII member header")
			}
			return value.trimmingCharacters(in: CharacterSet(charactersIn: " "))
		}
		func integer(_ start: Int, _ length: Int) throws -> Int {
			let value = try field(start, length)
			guard let number = Int(value.isEmpty ? "0" : value) else {
				throw ARError.badArchive("Invalid numeric member field")
			}
			return number
		}
		let sizeText = try field(48, 10)
		guard let size = Int(sizeText), size >= 0, size <= data.count - offset - 60 else {
			throw ARError.badArchive("Invalid or truncated member size")
		}
		let name = try field(0, 16)
		guard !name.isEmpty else { throw ARError.badArchive("Invalid name") }
		let dateText = try field(16, 12)
		guard let timestamp = Double(dateText.isEmpty ? "0" : dateText), timestamp.isFinite else {
			throw ARError.badArchive("Invalid member date")
		}
		return ARFileModel(
			name: name,
			modificationDate: Date(timeIntervalSince1970: timestamp),
			ownerId: try integer(28, 6),
			groupId: try integer(34, 6),
			mode: try integer(40, 8),
			size: size,
			content: data.subdata(in: offset + 60..<offset + 60 + size)
		)
	}
}

enum ARError: LocalizedError {
	case badArchive(String)

	var errorDescription: String? {
		switch self {
		case .badArchive(let reason): "Invalid DEB archive: \(reason)."
		}
	}
}
