import Foundation

/// Bound simultaneous copy/compression work, including jobs finishing after cancellation.
actor ArchivePreparationGate {
    static let shared = ArchivePreparationGate()
    private var active = 0
    private var waiting: [CheckedContinuation<Void, Never>] = []

    func acquire() async {
        if active < 2 {
            active += 1
        } else {
            await withCheckedContinuation { waiting.append($0) }
        }
    }

    func release() {
        if waiting.isEmpty {
            active -= 1
        } else {
            waiting.removeFirst().resume()
        }
    }
}
