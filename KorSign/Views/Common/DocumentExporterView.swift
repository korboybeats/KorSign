//
//  DocumentExporterView.swift
//  KorSign
//
//  Thin wrapper over UIDocumentPickerViewController(forExporting:) so SwiftUI can
//  present a "Save to Files" picker for one or more on-disk URLs.
//

import SwiftUI
import UIKit
import UniformTypeIdentifiers

struct DocumentExporterView: UIViewControllerRepresentable {
	let urls: [URL]
	/// Move (true) instead of copy. Tweak exports keep the original, so default is copy.
	var asCopy: Bool = true
	var onComplete: (() -> Void)? = nil
	/// Holds temporary files through picker completion or cancellation.
	var retaining: AnyObject? = nil

	func makeCoordinator() -> Coordinator { Coordinator(onComplete: onComplete, retaining: retaining) }

	func makeUIViewController(context: Context) -> UIDocumentPickerViewController {
		let picker = UIDocumentPickerViewController(forExporting: urls, asCopy: asCopy)
		// nil lets the picker reopen wherever the user last saved; otherwise pin to Documents.
		picker.directoryURL = UserDefaults.standard.bool(forKey: "KorSign.useLastExportLocation")
			? nil
			: FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first
		picker.delegate = context.coordinator
		return picker
	}

	func updateUIViewController(_ uiViewController: UIDocumentPickerViewController, context: Context) {}

	final class Coordinator: NSObject, UIDocumentPickerDelegate {
		let onComplete: (() -> Void)?
		let retaining: AnyObject?
		init(onComplete: (() -> Void)?, retaining: AnyObject?) {
			self.onComplete = onComplete
			self.retaining = retaining
		}

		func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
			onComplete?()
		}
		func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) {
			onComplete?()
		}
	}
}
