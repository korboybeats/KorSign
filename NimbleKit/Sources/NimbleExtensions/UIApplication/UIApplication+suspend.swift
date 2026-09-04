//
//  UIApplication+exitAndSuspend.swift
//  Loader
//
//  Created by samara on 13.03.2025.
//

import UIKit.UIApplication

extension UIApplication {
	/// Exit the application after an operation is complete
	public func suspend(exitAfterSuspending: Bool = true) {
		CFPreferencesAppSynchronize(kCFPreferencesCurrentApplication)
		let selector = #selector(NSXPCConnection.suspend)
		guard responds(to: selector) else { return }
		self.perform(selector)
		guard exitAfterSuspending else { return }
		DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
			exit(0)
		}
	}
	/// Exits the application and reopens
	public func suspendAndReopen() {
		suspend()
		UIApplication.openApp(with: Bundle.main.bundleIdentifier!)
	}
}
