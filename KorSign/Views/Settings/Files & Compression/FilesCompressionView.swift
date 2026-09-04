//
//  FilesCompressionView.swift
//  KorSign
//
//  Created by samara on 6.05.2025.
//

import SwiftUI
import Zip
import NimbleViews

// MARK: - View
struct FilesCompressionView: View {
	@AppStorage("Feather.compressionLevel") private var _compressionLevel: Int = ZipCompression.DefaultCompression.rawValue
	@AppStorage("Feather.useShareSheetForArchiving") private var _useShareSheet: Bool = false
	@AppStorage(ArchiveBackend.storageKey) private var _backend: Int = ArchiveBackend.zip.rawValue
	@AppStorage("KorSign.useLastExportLocation") private var _useLastExportLocation: Bool = false
	@AppStorage("KorSign.libraryDefaultImportAction") private var _defaultImportAction: String = "files"

	// MARK: Body
    var body: some View {
		NBList(.localized("Files & Compression")) {
			Section {
				Picker(.localized("Compression Level"), systemImage: "archivebox", selection: $_compressionLevel) {
					ForEach(ZipCompression.allCases, id: \.rawValue) { level in
						Text(level.label).tag(level)
					}
				}
				Picker(.localized("Compression Engine"), systemImage: "shippingbox", selection: $_backend) {
					ForEach(ArchiveBackend.allCases, id: \.rawValue) { backend in
						Text(backend.label).tag(backend.rawValue)
					}
				}
			} footer: {
				Text(.localized("The engine used to pack signed apps into IPAs. ZIPFoundation can be a more reliable fallback if Zip fails."))
			}

			Section {
				Toggle(.localized("Show Sheet when Exporting"), systemImage: "square.and.arrow.up", isOn: $_useShareSheet)
			} footer: {
				Text(.localized("Toggling show sheet will present a share sheet after exporting to your files."))
			}

			Section {
				Toggle(.localized("Remember Last Export Location"), systemImage: "clock.arrow.circlepath", isOn: $_useLastExportLocation)
			} footer: {
				Text(.localized("Reopen the Save to Files picker at the last folder you used instead of always starting at the KorSign documents folder."))
			}

			Section {
				NavigationLink(destination: ImportFoldersView()) {
					Label(.localized("Import Folders"), systemImage: "folder")
				}
			} footer: {
				Text(.localized("Choose which folder each kind of import opens in."))
			}

			Section {
				Picker(.localized("Plus Button Import"), systemImage: "plus", selection: $_defaultImportAction) {
					Text(.localized("Import from Files")).tag("files")
					Text(.localized("Import Multiple Files")).tag("multipleFiles")
					Text(.localized("Import from URL")).tag("url")
				}
			} footer: {
				Text(.localized("Choose what tapping the Library plus button opens. Touch and hold the button to choose another import option."))
			}
		}
    }
}
