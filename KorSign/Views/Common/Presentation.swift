//
//  Presentation.swift
//  KorSign
//
//  Created by Ryuk
//

import UIKit
import NimbleExtensions

/// Defers work until nothing is mid transition. SwiftUI drops a sheet set while a menu, alert or
/// picker is still dismissing.
@MainActor
enum Presentation {
	private static let _tick = 0.05
	private static let _maxTicks = 30

	static func afterDismiss(_ work: @escaping () -> Void) {
		// Let the action that requested dismissal finish before inspecting transitions.
		DispatchQueue.main.async {
			guard let root = UIApplication.shared.keyWindow?.rootViewController else { return work() }
			_wait(root, 0, work)
		}
	}

	private static func _wait(_ root: UIViewController, _ tick: Int, _ work: @escaping () -> Void) {
		let top = _topmost(root)
		guard top.isBeingDismissed || top.transitionCoordinator != nil, tick < _maxTicks else { return work() }
		DispatchQueue.main.asyncAfter(deadline: .now() + _tick) { _wait(root, tick + 1, work) }
	}

	private static func _topmost(_ controller: UIViewController) -> UIViewController {
		controller.presentedViewController.map(_topmost) ?? controller
	}
}
