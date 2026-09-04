//
//  ZsignHandler.swift
//  KorSign
//
//  Created by samara on 17.04.2025.
//

import Foundation
import Zsign
import UIKit

final class ZsignHandler {
	private var _appUrl: URL
	private var _options: Options
	private var _certificate: CertificatePair?
	
	init(
		appUrl: URL,
		options: Options = OptionsManager.shared.options,
		cert: CertificatePair? = nil
	) {
		self._appUrl = appUrl
		self._options = options
		self._certificate = cert
	}
	
	func disinject() async throws {
		guard !_options.disInjectionFiles.isEmpty else {
			return
		}
		
		SigningLog.shared.info(.localized("Removing injected dylibs"))

		let bundle = Bundle(url: _appUrl)
		let execPath = _appUrl.appendingPathComponent(bundle?.exec ?? "").relativePath

		if !Zsign.removeDylibs(appExecutable: execPath, using: _options.disInjectionFiles) {
			throw SigningFileHandlerError.disinjectFailed
		}
	}
	
	func sign() async throws {
		guard let cert = _certificate else {
			throw SigningFileHandlerError.missingCertifcate
		}

		StdoutCapture.shared.start { SigningLog.shared.info($0) }
		defer { StdoutCapture.shared.stop() }

		let credentials = await MainActor.run {
			(Storage.shared.getFile(.provision, from: cert)?.path ?? "",
			 Storage.shared.getFile(.certificate, from: cert)?.path ?? "", cert.password ?? "")
		}

		guard Zsign.sign(
			appPath: _appUrl.relativePath,
			provisionPath: credentials.0,
			p12Path: credentials.1,
			p12Password: credentials.2,
			entitlementsPath: _options.appEntitlementsFile?.path ?? "",
			removeProvision: !_options.removeProvisioning,
			completion: { _ in } // The native bridge requires a callback; its return value covers early failures too.
		) else {
			throw SigningFileHandlerError.signFailed
		}
	}
	
	func adhocSign() async throws {
		StdoutCapture.shared.start { SigningLog.shared.info($0) }
		defer { StdoutCapture.shared.stop() }

		guard Zsign.sign(
			appPath: _appUrl.relativePath,
			entitlementsPath: _options.appEntitlementsFile?.path ?? "",
			adhoc: true,
			removeProvision: !_options.removeProvisioning,
			completion: { _ in } // The native bridge requires a callback; its return value covers early failures too.
		) else {
			throw SigningFileHandlerError.signFailed
		}
	}
}
