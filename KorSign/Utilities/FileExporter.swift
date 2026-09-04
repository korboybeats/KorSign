//
//  FileExporter.swift
//  KorSign
//
//  Created by Ryuk
//

import Foundation
import Zip

enum FileExporter {
	/// A file shares as-is; a directory bundle (e.g. `.framework`) has to be zipped first.
	static func shareableURL(for source: URL) -> (url: URL, owner: TemporaryExport?)? {
		let isDirectory = (try? source.resourceValues(forKeys: [.isDirectoryKey]))?.isDirectory ?? false
		guard isDirectory else { return (source, nil) }

		do {
			let export = try TemporaryExport(fileName: "\(source.lastPathComponent).zip")
			try Zip.zipFiles(paths: [source], zipFilePath: export.url, password: nil, progress: nil)
			return (export.url, export)
		} catch {
			return nil
		}
	}
}
