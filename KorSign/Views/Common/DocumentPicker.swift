//
//  DocumentPicker.swift
//  KorSign
//
//  Created by Ryuk
//

import UIKit
import UniformTypeIdentifiers
import NimbleExtensions

/// UIKit presented. In a SwiftUI `.sheet` the picker dismisses itself and desyncs the binding,
/// which then swallows later presentations.
@MainActor
enum DocumentPicker {
	static func open(
		_ types: [UTType],
		multiple: Bool = false,
		folder: ImportFolder? = nil,
		onPick: @escaping ([URL]) -> Void
	) {
		let picker = UIDocumentPickerViewController(forOpeningContentTypes: types, asCopy: true)
		picker.allowsMultipleSelection = multiple
		_present(picker, folder: folder) { urls in
			guard !urls.isEmpty else { return }
			onPick(urls)
		}
	}

	// Exports continue using DocumentExporterView, which retains temporary files.

	private static var _delegates: [ObjectIdentifier: Delegate] = [:]

	private static func _present(
		_ picker: UIDocumentPickerViewController,
		folder: ImportFolder?,
		onFinish: @escaping ([URL]) -> Void
	) {
		Presentation.afterDismiss {
			guard let presenter = UIApplication.topViewController(),
				!presenter.isBeingDismissed, !presenter.isBeingPresented,
				!(presenter is UIDocumentPickerViewController) else { return }

			let key = ObjectIdentifier(picker)
			let delegate = Delegate(folder: folder) { urls in
				Presentation.afterDismiss {
					_delegates[key] = nil
					onFinish(urls)
				}
			}
			if let directory = delegate.startDirectory { picker.directoryURL = directory }
			picker.delegate = delegate
			picker.presentationController?.delegate = delegate
			_delegates[key] = delegate

			presenter.present(picker, animated: true)
		}
	}

	private final class Delegate: NSObject, UIDocumentPickerDelegate, UIAdaptivePresentationControllerDelegate {
		let startDirectory: URL?
		private let _finish: ([URL]) -> Void
		private var _scoped: URL?
		private var _finished = false

		init(folder: ImportFolder?, finish: @escaping ([URL]) -> Void) {
			_finish = finish
			startDirectory = folder.flatMap(Self._bookmarked)
			super.init()
			// Scope must stay held while presented or directoryURL is ignored.
			if let url = startDirectory, url.startAccessingSecurityScopedResource() { _scoped = url }
		}

		func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
			_end(urls)
		}

		func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) {
			_end([])
		}

		func presentationControllerDidDismiss(_ presentationController: UIPresentationController) {
			_end([])
		}

		private func _end(_ urls: [URL]) {
			guard !_finished else { return }
			_finished = true
			_scoped?.stopAccessingSecurityScopedResource()
			_scoped = nil
			_finish(urls)
		}

		private static func _bookmarked(_ folder: ImportFolder) -> URL? {
			guard let data = UserDefaults.standard.data(forKey: folder.bookmarkKey) else { return nil }
			var stale = false
			return try? URL(resolvingBookmarkData: data, bookmarkDataIsStale: &stale)
		}
	}
}
