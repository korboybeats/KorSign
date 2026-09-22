import SwiftUI
import UIKit

/// Observe the first touch without recognizing a gesture or replacing native actions.
struct TabTouchHaptics: UIViewControllerRepresentable {
    func makeUIViewController(context: Context) -> Observer { Observer() }

    func updateUIViewController(_ controller: Observer, context: Context) {
        controller.scheduleAttachment()
    }

    static func dismantleUIViewController(_ controller: Observer, coordinator: ()) {
        controller.detach()
    }

    final class Observer: UIViewController {
        private weak var observedBar: UITabBar?
        private let touchObserver = TouchObserver()
        private var attachment: DispatchWorkItem?

        override func loadView() {
            view = UIView()
            view.isUserInteractionEnabled = false
        }

        override func viewDidAppear(_ animated: Bool) {
            super.viewDidAppear(animated)
            scheduleAttachment()
        }

        override func viewDidLayoutSubviews() {
            super.viewDidLayoutSubviews()
            attach()
        }

        func scheduleAttachment() {
            attachment?.cancel()
            let work = DispatchWorkItem { [weak self] in self?.attach() }
            attachment = work
            DispatchQueue.main.async(execute: work)
        }

        func detach() {
            attachment?.cancel()
            observedBar?.removeGestureRecognizer(touchObserver)
            observedBar = nil
        }

        private func attach() {
            guard let root = view.window?.rootViewController,
                  let tabBar = findTabBar(in: root), observedBar !== tabBar else { return }
            observedBar?.removeGestureRecognizer(touchObserver)
            touchObserver.cancelsTouchesInView = false
            touchObserver.delaysTouchesBegan = false
            touchObserver.delaysTouchesEnded = false
            tabBar.addGestureRecognizer(touchObserver)
            observedBar = tabBar
        }

        private func findTabBar(in controller: UIViewController) -> UITabBar? {
            if let tabs = controller as? UITabBarController { return tabs.tabBar }
            for child in controller.children {
                if let bar = findTabBar(in: child) { return bar }
            }
            return nil
        }

    }

    final class TouchObserver: UIGestureRecognizer {
        override func canPrevent(_ preventedGestureRecognizer: UIGestureRecognizer) -> Bool { false }
        override func canBePrevented(by preventingGestureRecognizer: UIGestureRecognizer) -> Bool { false }

        override func touchesBegan(_ touches: Set<UITouch>, with event: UIEvent) {
            defer { state = .failed } // Observe only; never claim the touch sequence.
            guard let bar = view, let touch = touches.first,
                  containsEnabledControl(in: bar, point: touch.location(in: bar)) else { return }
            AppHaptics.tabTouch()
        }

        private func containsEnabledControl(in view: UIView, point: CGPoint) -> Bool {
            guard !view.isHidden, view.alpha > 0.01 else { return false }
            if let control = view as? UIControl, control.isEnabled,
               control.bounds.contains(point) { return true }
            return view.subviews.contains {
                containsEnabledControl(in: $0, point: $0.convert(point, from: view))
            }
        }
    }
}
