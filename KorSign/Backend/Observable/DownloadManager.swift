//
//  DownloadManager.swift
//  KorSign
//
//  Created by samara on 3.05.2025.
//

import Foundation
import Combine
import UIKit
import UserNotifications
import BackgroundTasks
import ActivityKit

class DownloadManager: NSObject, ObservableObject {
	static let shared = DownloadManager()

	protocol ErrorDelegate: AnyObject {
		func showUIErrorMessage(title: String, message: String)
	}
	
	weak var errorDelegate: ErrorDelegate?
	
	@Published var downloads: [Download] = []
	@Published var currentDownloadSpeed: Int64 = 0

	var manualDownloads: [Download] {
		downloads.filter { isManualDownload($0.id) }
	}

	var activeNetworkDownloads: [Download] {
		downloads.filter { !$0.onlyArchiving && ($0.isActive || $0.progress > 0) && $0.progress < 1.0 && !$0.isPaused }
	}

	/// Unpacking or auto signing. Both hold the keep-alive open.
	var processingDownloads: [Download] {
		downloads.filter { $0.phase == .importing || $0.phase == .signing }
	}

	var hasUnfinishedWork: Bool {
		downloads.contains { $0.isActive || $0.isImporting || $0.isSigning || ($0.progress > 0 && $0.progress < 1.0) }
	}

	var _backgroundSession: URLSession!
	var _foregroundSession: URLSession!
	var backgroundCompletionHandler: (() -> Void)?

	var isAppInBackground = false
	var backgroundEntryTime: Date?

	var backgroundTaskManager: BackgroundTaskManager?
	private var importObservers: [String: AnyCancellable] = [:]
	var progressUpdateTimer: Timer?

	// `Any?` so the property carries no availability requirement (ActivityKit is 16.1+, app deploys to 16.0).
	var downloadActivity: Any?

	@available(iOS 16.2, *)
	var _downloadActivity: Activity<DownloadActivityAttributes>? {
		get { downloadActivity as? Activity<DownloadActivityAttributes> }
		set { downloadActivity = newValue }
	}
	var lastUpdateTime: Date = Date()
	var updateThrottle: TimeInterval = 2.0

	/// Makes the next Live Activity / progress notification skip the update throttle.
	func forceNextProgressUpdate() { lastUpdateTime = .distantPast }
	var activityStateTask: Task<Void, Never>?
	// Guards the race where a Live Activity is mid-creation (`downloadActivity == nil`) and the
	// progress timer would otherwise post a fallback notification.
	var isCreatingLiveActivity = false

	private var speedTracker = DownloadSpeedTracker()

	var completedDownloadNames: [String] = []
	var isActivityShowingCompletion = false

	// Every download in this Live Activity session, incl. ones downloaded but not yet archived.
	var allActivityDownloads: [String: (fileName: String, downloaded: Int64, total: Int64)] = [:]

	// Downloads that finished downloading (X in the X/Y counter) — distinct from archiving completion.
	var finishedDownloadingIDs: Set<String> = []

	override init() {
		super.init()

		let foregroundConfig = URLSessionConfiguration.default
		foregroundConfig.timeoutIntervalForRequest = 300 // 5 min
		foregroundConfig.timeoutIntervalForResource = 7200 // 2 hours
		foregroundConfig.httpShouldUsePipelining = true
		foregroundConfig.allowsExpensiveNetworkAccess = true
		foregroundConfig.allowsConstrainedNetworkAccess = true
		foregroundConfig.httpMaximumConnectionsPerHost = 10
		foregroundConfig.multipathServiceType = .handover
		foregroundConfig.waitsForConnectivity = false

		_foregroundSession = URLSession(configuration: foregroundConfig, delegate: self, delegateQueue: .main)

		let backgroundConfig: URLSessionConfiguration = URLSessionConfiguration.background(withIdentifier: "ryuk2.anoxclan.com.background")
		backgroundConfig.isDiscretionary = false // don't wait for ideal conditions
		backgroundConfig.sessionSendsLaunchEvents = true
		backgroundConfig.shouldUseExtendedBackgroundIdleMode = false
		backgroundConfig.timeoutIntervalForRequest = 300 // 5 min
		backgroundConfig.timeoutIntervalForResource = 7200 // 2 hours
		backgroundConfig.httpShouldUsePipelining = true
		backgroundConfig.allowsExpensiveNetworkAccess = true
		backgroundConfig.allowsConstrainedNetworkAccess = true
		backgroundConfig.httpMaximumConnectionsPerHost = 10
		backgroundConfig.waitsForConnectivity = false
		backgroundConfig.networkServiceType = .responsiveData

		_backgroundSession = URLSession(configuration: backgroundConfig, delegate: self, delegateQueue: .main)

		requestNotificationPermissions()

		NotificationCenter.default.addObserver(
			self,
			selector: #selector(appWillEnterBackground),
			name: UIApplication.willResignActiveNotification,
			object: nil
		)
		
		NotificationCenter.default.addObserver(
			self,
			selector: #selector(appDidBecomeActive),
			name: UIApplication.didBecomeActiveNotification,
			object: nil
		)
		
		NotificationCenter.default.addObserver(
			self,
			selector: #selector(appWillTerminate),
			name: UIApplication.willTerminateNotification,
			object: nil
		)

		// Live Activity control notifications from the widget extension.
		NotificationCenter.default.addObserver(
			self,
			selector: #selector(handlePauseDownloadsNotification),
			name: NSNotification.Name("PauseDownloads"),
			object: nil
		)

		NotificationCenter.default.addObserver(
			self,
			selector: #selector(handleResumeDownloadsNotification),
			name: NSNotification.Name("ResumeDownloads"),
			object: nil
		)
	}

	deinit {
		NotificationCenter.default.removeObserver(self)
	}
	
	// Audio sessions can only be activated while the app is still foreground.
	private func ensureKeepAlive() {
		guard backgroundTaskManager == nil else { return }

		let manager = BackgroundTaskManager(
			taskName: "DownloadManager",
			expirationTitle: "Downloads continuing",
			expirationBody: "Downloads and imports continue in the background"
		)
		manager.start()
		backgroundTaskManager = manager
		startProgressTimer()
	}

	private func releaseKeepAliveIfIdle() {
		guard !hasUnfinishedWork else { return }
		backgroundTaskManager?.stop()
		backgroundTaskManager = nil
		endProgressTimer()
	}

	func beginImport(for download: Download) {
		download.beginImport()

		// Unpacking has no session callbacks to piggyback on.
		importObservers[download.id] = download.$unpackageProgress
			.receive(on: DispatchQueue.main)
			.sink { [weak self] _ in
				self?.updateLiveActivity(activeDownloads: [])
			}

		if isAppInBackground { ensureKeepAlive() }
	}

	func endImport(for download: Download) {
		importObservers.removeValue(forKey: download.id)
		download.endImport()
	}

	private func requestNotificationPermissions() {
		UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge, .providesAppNotificationSettings]) { granted, error in
			if granted {
			} else if let error = error {
			}
		}
		
		UNUserNotificationCenter.current().delegate = self
	}
	
	@objc private func appWillEnterBackground() {
		isAppInBackground = true
		backgroundEntryTime = Date()

		if hasUnfinishedWork { ensureKeepAlive() }
	}

	@objc private func appDidBecomeActive() {
		isAppInBackground = false
		backgroundEntryTime = nil

		backgroundTaskManager?.stop()
		backgroundTaskManager = nil

		UNUserNotificationCenter.current().removeAllDeliveredNotifications()

		let hasActiveDownloads = downloads.contains { download in
			(download.isActive && !download.isPaused) ||
			(download.progress > 0 && download.progress < 1.0 && !download.isPaused) ||
			(download.unpackageProgress > 0 && download.unpackageProgress < 1.0)
		}

		let hasPausedDownloads = downloads.contains { download in
			download.isPaused && download.progress > 0 && download.progress < 1.0
		}

		if downloadActivity != nil && !hasActiveDownloads && !hasPausedDownloads && processingDownloads.isEmpty {
			dismissLiveActivityImmediately()
			completedDownloadNames = []
			isActivityShowingCompletion = false
			allActivityDownloads = [:] 
			finishedDownloadingIDs = []
		}

		processPendingDownloads()

		for download in downloads where download.isPaused {
			resumeDownload(download)
		}

		let pausedDownloads = downloads.filter { $0.isPaused }
		if !pausedDownloads.isEmpty && downloadActivity != nil {
			let activeDownloads = self.downloads.filter {
				($0.progress > 0 && $0.progress < 1.0) ||
				($0.unpackageProgress > 0 && $0.unpackageProgress < 1.0)
			}
			if !activeDownloads.isEmpty {
				self.forceNextProgressUpdate()
				self.updateLiveActivity(activeDownloads: activeDownloads)
			}
		}
	}
	
	@objc private func handlePauseDownloadsNotification() {
		DispatchQueue.main.async {
			self.pauseAllDownloads()
		}
	}

	@objc private func handleResumeDownloadsNotification() {
		DispatchQueue.main.async {
			self.resumeAllDownloads()
		}
	}

	@objc private func appWillTerminate() {
		// Must finish fast (synchronous, time-limited) to avoid watchdog termination.
		backgroundTaskManager?.stop()
		backgroundTaskManager = nil

		endProgressTimer()

		if #available(iOS 16.2, *), let activity = _downloadActivity {
			Task {
				await activity.end(nil, dismissalPolicy: .immediate)
			}
			downloadActivity = nil
		}

		let saveGroup = DispatchGroup()
		let deadline = DispatchTime.now() + .milliseconds(500)

		for download in downloads {
			if let task = download.task, task.state == .running {
				saveGroup.enter()
				task.cancel { resumeData in
					download.resumeData = resumeData
					self.saveResumeData(for: download)
					saveGroup.leave()
				}
			}
		}

		_ = saveGroup.wait(timeout: deadline)
	}
	
	
	private func startProgressTimer() {
		guard progressUpdateTimer == nil else { return }

		let timer = Timer(timeInterval: 1.0, repeats: true) { [weak self] _ in
			self?.handleProgressTick()
		}

		RunLoop.main.add(timer, forMode: .common)
		progressUpdateTimer = timer
	}

	private func endProgressTimer() {
		progressUpdateTimer?.invalidate()
		progressUpdateTimer = nil
	}

	private func handleProgressTick() {
		sampleDownloadSpeed()

		if isAppInBackground {
			updateMergedProgressNotification()
		} else if activeNetworkDownloads.isEmpty && processingDownloads.isEmpty {
			endProgressTimer()
		}
	}

	private func sampleDownloadSpeed() {
		guard !activeNetworkDownloads.isEmpty else {
			speedTracker.reset()
			if currentDownloadSpeed != 0 { currentDownloadSpeed = 0 }
			return
		}

		// Finished downloads stay in the sum to keep the total monotonic.
		let totalBytes = downloads.reduce(Int64(0)) { $0 + ($1.onlyArchiving ? 0 : $1.bytesDownloaded) }
		let speed = speedTracker.sample(totalBytes: totalBytes)
		if currentDownloadSpeed != speed { currentDownloadSpeed = speed }
	}
	
	private func processPendingDownloads() {
		for download in downloads where !download.isImporting {
			guard let pendingURL = download.pendingFileURL else { continue }
			try? handlePackageFile(url: pendingURL, dl: download)
		}
	}
	
	func saveResumeData(for download: Download) {
		let documentsPath = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
		let resumeDataPath = documentsPath.appendingPathComponent("ResumeData_\(download.id).data")
		
		if let resumeData = download.resumeData {
			try? resumeData.write(to: resumeDataPath)
		} else {
			try? FileManager.default.removeItem(at: resumeDataPath)
		}
	}
	
	private func loadResumeData(for download: Download) -> Data? {
		let documentsPath = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
		let resumeDataPath = documentsPath.appendingPathComponent("ResumeData_\(download.id).data")
		
		return try? Data(contentsOf: resumeDataPath)
	}
	
	// MARK: - Notification Methods

	func updateMergedProgressNotification() {
		// Actively downloading only — archiving doesn't show progress notifications.
		let activeDownloads = downloads.filter {
			(($0.isActive || $0.progress > 0) && $0.progress < 1.0 && !$0.isPaused)
		}

		let pausedDownloads = downloads.filter {
			$0.progress > 0 && $0.progress < 1.0 && $0.isPaused
		}

		guard !activeDownloads.isEmpty || !pausedDownloads.isEmpty else {
			UNUserNotificationCenter.current().removeDeliveredNotifications(withIdentifiers: ["merged_download_progress"])

			guard processingDownloads.isEmpty else {
				updateLiveActivity(activeDownloads: [])
				return
			}

			endLiveActivity()

			releaseKeepAliveIfIdle()

			return
		}

		// Imports (onlyArchiving) are excluded — no network bytes, they'd show a phantom 0% entry.
		if activeDownloads.isEmpty && !pausedDownloads.isEmpty {
			updateLiveActivityWithPausedState(activeDownloads: pausedDownloads)
		} else {
			let downloadingOnly = downloads.filter { !$0.onlyArchiving && $0.progress > 0 && $0.progress < 1.0 && !$0.isPaused }
			updateLiveActivity(activeDownloads: downloadingOnly)
		}

		// Live Activities are the primary progress UI; only fall back to a local notification when
		// they're genuinely unavailable. (Don't branch on `downloadActivity != nil` — it's
		// momentarily false mid-creation, which would race a stray notification onscreen.)
		if #available(iOS 16.2, *), ActivityAuthorizationInfo().areActivitiesEnabled {
			if downloadActivity == nil && !isCreatingLiveActivity {
				startLiveActivityIfNeeded()
			}
			UNUserNotificationCenter.current().removeDeliveredNotifications(withIdentifiers: ["merged_download_progress"])
			return
		}

		// Network downloads only — imports must not produce a stuck 0% notification.
		let notifiableDownloads = activeDownloads.filter { !$0.onlyArchiving }
		guard !notifiableDownloads.isEmpty else {
			UNUserNotificationCenter.current().removeDeliveredNotifications(withIdentifiers: ["merged_download_progress"])
			return
		}

		let content = UNMutableNotificationContent()

		if notifiableDownloads.count == 1 {
			let download = notifiableDownloads[0]
			let percent = Int(download.progress * 100)
			let bytesFormatted = formatBytes(download.bytesDownloaded)
			let totalFormatted = formatBytes(download.totalBytes)

			content.title = download.fileName
			content.body = "\(bytesFormatted) / \(totalFormatted)"
			content.subtitle = "Progress: \(percent)%"
		} else {
			let totalProgress = notifiableDownloads.reduce(0.0) { $0 + $1.progress }
			let averageProgress = totalProgress / Double(notifiableDownloads.count)
			let percent = Int(averageProgress * 100)

			let totalBytesDownloaded = notifiableDownloads.reduce(Int64(0)) { $0 + $1.bytesDownloaded }
			let totalBytesExpected = notifiableDownloads.reduce(Int64(0)) { $0 + $1.totalBytes }

			let bytesFormatted = formatBytes(totalBytesDownloaded)
			let totalFormatted = formatBytes(totalBytesExpected)

			content.title = "Downloading \(notifiableDownloads.count) files"
			content.subtitle = "Overall Progress: \(percent)%"
			content.body = "\(bytesFormatted) / \(totalFormatted)"
		}

		content.sound = nil
		content.interruptionLevel = .passive

		let request = UNNotificationRequest(
			identifier: "merged_download_progress",
			content: content,
			trigger: nil
		)

		UNUserNotificationCenter.current().add(request)
	}
	
	func sendSystemNotification(title: String, body: String, identifier: String) {
		let content = UNMutableNotificationContent()
		content.title = title
		content.body = body
		content.sound = .default
		
		let request = UNNotificationRequest(
			identifier: identifier,
			content: content,
			trigger: nil
		)
		
		UNUserNotificationCenter.current().add(request)
	}
	
	func sendCompletionNotification(for download: Download, status: String) {
		let content = UNMutableNotificationContent()
		content.title = status
		content.body = download.fileName
		content.sound = .default
		content.interruptionLevel = .timeSensitive
		
		let request = UNNotificationRequest(
			identifier: "completion_\(download.id)",
			content: content,
			trigger: nil
		)
		
		UNUserNotificationCenter.current().add(request)
	}

	func showUIErrorMessage(for download: Download, error: NSError) {
		DispatchQueue.main.async {
			let generator = UINotificationFeedbackGenerator()
			generator.notificationOccurred(.error)

			self.errorDelegate?.showUIErrorMessage(
				title: "Failed to download ipa",
				message: error.localizedDescription
			)
		}
	}
	
	// MARK: - Helper Methods
	
	private func formatBytes(_ bytes: Int64) -> String {
		let formatter = ByteCountFormatter()
		formatter.countStyle = .binary
		return formatter.string(fromByteCount: bytes)
	}
	
	// MARK: - Public Methods
	
	func startDownload(from url: URL, id: String = UUID().uuidString, appName: String? = nil, appDescription: String? = nil) -> Download {
        if !Thread.isMainThread {
            return DispatchQueue.main.sync { self.startDownload(from: url, id: id, appName: appName, appDescription: appDescription) }
        }
        if let existingDownload = downloads.first(where: { $0.url == url || $0.id == id }) {
            resumeDownload(existingDownload)
            return existingDownload
        }

        let download = Download(id: id, url: url, appName: appName, appDescription: appDescription)
        download.isActive = true

		let session = isAppInBackground ? _backgroundSession! : _foregroundSession!

		var request = URLRequest(url: url)
		request.cachePolicy = .reloadIgnoringLocalAndRemoteCacheData
		request.networkServiceType = .responsiveData
		request.allowsExpensiveNetworkAccess = true
		request.allowsConstrainedNetworkAccess = true
		request.setValue("gzip, deflate, br", forHTTPHeaderField: "Accept-Encoding")

		let task = session.downloadTask(with: request)
		download.task = task
		task.priority = 1.0
		objectWillChange.send()
		downloads.append(download)
		saveResumeData(for: download)
		task.resume()

		DispatchQueue.main.async {
			guard self.downloads.contains(where: { $0 === download }) else { return }
			self.startProgressTimer()

			if self.isAppInBackground {
				self.ensureKeepAlive()
			}

			// BGContinuedProcessingTask keeps work going in the background on iOS 19+.
			if #available(iOS 19.0, *) {
				if let appDelegate = UIApplication.shared.delegate as? AppDelegate {
					appDelegate.submitContinuedProcessingTask()
				}
			}

			Task {
				self.startLiveActivityIfNeeded()
			}
		}

		return download
	}
	
	func startArchive(from url: URL, id: String = UUID().uuidString, appName: String? = nil, completion: ((Error?) -> Void)? = nil) -> Download {
		let download = Download(id: id, url: url, onlyArchiving: true, appName: appName)
		download.isActive = true

		DispatchQueue.main.async {
			self.objectWillChange.send()
			self.downloads.append(download)
			self.beginImport(for: download)
		}

		DispatchQueue.global().async {
			FR.handlePackageFile(url, download: download) { result in
				switch result {
				case .failure(let error):
					UINotificationFeedbackGenerator().notificationOccurred(.error)

					if let completion = completion {
						// Caller owns the error UI; don't also fire the generic delegate alert.
						DispatchQueue.main.async { completion(error) }
					} else if !self.isAppInBackground {
						self.errorDelegate?.showUIErrorMessage(
							title: "Import Failed",
							message: error.localizedDescription
						)
					}

					DispatchQueue.main.async { self.finishImport(of: download, succeeded: false) }
				case .success(let app):
					DispatchQueue.main.async {
						self.objectWillChange.send()
						download.unpackageProgress = 1.0
						completion?(nil)
						self.autoSignOrFinish(app, for: download)
					}
				}
			}
		}

		return download
	}
	
	func resumeDownload(_ download: Download) {
		if !Thread.isMainThread {
			DispatchQueue.main.async { self.resumeDownload(download) }
			return
		}
		guard downloads.contains(where: { $0 === download }), download.isPaused,
			!download.onlyArchiving, !download.isImporting, !download.isSigning,
			download.pendingFileURL == nil else { return }
		if download.isPausing {
			download.resumeAfterPause = true
			return
		}
		let resumeData = download.resumeData ?? loadResumeData(for: download)
		let session = isAppInBackground ? _backgroundSession! : _foregroundSession!
		let previous = download.task
		download.task = nil
		previous?.cancel()
		let task: URLSessionDownloadTask
		if let resumeData {
			task = session.downloadTask(withResumeData: resumeData)
		} else {
			task = session.downloadTask(with: URLRequest(url: download.url))
			download.progress = 0
			download.bytesDownloaded = 0
		}
		download.resumeData = nil
		saveResumeData(for: download)
		download.task = task
		download.isActive = true
		download.isPaused = false
		download.resumeAfterPause = false
		task.resume()

		DispatchQueue.main.async {
			self.startProgressTimer()

			let activeDownloads = self.downloads.filter {
				($0.progress > 0 && $0.progress < 1.0) ||
				($0.unpackageProgress > 0 && $0.unpackageProgress < 1.0)
			}
			if !activeDownloads.isEmpty && self.downloadActivity != nil {
				self.forceNextProgressUpdate()
				self.updateLiveActivity(activeDownloads: activeDownloads)
			}
		}
	}

	func pauseDownload(_ download: Download) {
		if !Thread.isMainThread {
			DispatchQueue.main.async { self.pauseDownload(download) }
			return
		}
		guard downloads.contains(where: { $0 === download }), !download.onlyArchiving,
			!download.isImporting, !download.isSigning, download.pendingFileURL == nil else { return }
		download.resumeAfterPause = false
		guard !download.isPaused, let task = download.task else { return }
		download.isPaused = true
		download.isActive = false
		download.isPausing = true
		task.cancel { resumeData in
			DispatchQueue.main.async {
				guard self.downloads.contains(where: { $0 === download }), download.task === task else { return }
				download.task = nil
				download.isPausing = false
				download.resumeData = resumeData
				self.saveResumeData(for: download)
				if download.resumeAfterPause { self.resumeDownload(download) }
			}
		}
	}
	
	func cancelDownload(_ download: Download) {
		if !Thread.isMainThread {
			DispatchQueue.main.async { self.cancelDownload(download) }
			return
		}
		guard downloads.contains(where: { $0 === download }),
			!download.isImporting, !download.isSigning else { return }
		let task = download.task
		download.task = nil
		download.isPausing = false
		download.resumeAfterPause = false
		download.isPaused = false
		download.isActive = false
		download.resumeData = nil
		saveResumeData(for: download)
		task?.cancel()
		download.removeStagedFiles()

		if let index = self.downloads.firstIndex(where: { $0 === download }) {
			self.objectWillChange.send()

			// Drop from tracking so a manually stopped download leaves overall progress.
			self.allActivityDownloads.removeValue(forKey: download.id)
			self.finishedDownloadingIDs.remove(download.id)

			self.downloads.remove(at: index)

			let remainingActiveDownloads = self.downloads.filter {
				$0.progress > 0 && $0.progress < 1.0 && !$0.isPaused
			}

			if !remainingActiveDownloads.isEmpty && self.downloadActivity != nil {
				self.forceNextProgressUpdate()
				self.updateLiveActivity(activeDownloads: remainingActiveDownloads)
			} else {
				self.endLiveActivity()
			}

			self.releaseKeepAliveIfIdle()
		}
	}
	
	func pauseAllDownloads() {
		for download in downloads {
			pauseDownload(download)
		}
		
		DispatchQueue.main.async {
			let activeDownloads = self.downloads.filter {
				($0.progress > 0 && $0.progress < 1.0) ||
				($0.unpackageProgress > 0 && $0.unpackageProgress < 1.0)
			}
			if !activeDownloads.isEmpty && self.downloadActivity != nil {
				self.forceNextProgressUpdate()
				self.updateLiveActivity(activeDownloads: activeDownloads)
			}
		}
	}
	
	func resumeAllDownloads() {
		for download in downloads where download.isPaused {
			resumeDownload(download)
		}

		if isAppInBackground && hasUnfinishedWork {
			ensureKeepAlive()
		}
	}
	
	func isManualDownload(_ string: String) -> Bool {
		return string.contains("FeatherManualDownload")
	}
	
	func getDownload(by id: String) -> Download? {
		return downloads.first(where: { $0.id == id })
	}
	
	func getDownloadIndex(by id: String) -> Int? {
		return downloads.firstIndex(where: { $0.id == id })
	}
	
	func getDownloadTask(by task: URLSessionDownloadTask) -> Download? {
		return downloads.first(where: { $0.task === task })
	}
	
	var nonManualDownloads: [Download] {
		downloads.filter { !isManualDownload($0.id) }
	}

	func handlePackageFile(url: URL, dl: Download) throws {
		guard !dl.isImporting else { return }

		objectWillChange.send()
		dl.progress = 1.0
		// Claim the input before any subsequent lifecycle callback can retry it.
		dl.pendingFileURL = url
		beginImport(for: dl)

		FR.handlePackageFile(url, download: dl) { result in
			switch result {
			case .failure(let error):
				UINotificationFeedbackGenerator().notificationOccurred(.error)

				if self.isAppInBackground {
					self.sendCompletionNotification(for: dl, status: "❌ Import failed: \(error.localizedDescription)")
				} else {
					self.errorDelegate?.showUIErrorMessage(
						title: "Import Failed",
						message: error.localizedDescription
					)
				}

				DispatchQueue.main.async { self.finishImport(of: dl, succeeded: false) }
			case .success(let app):
				DispatchQueue.main.async {
					self.objectWillChange.send()
					dl.unpackageProgress = 1.0
					self.autoSignOrFinish(app, for: dl)
				}
			}
		}
	}

	private func autoSignOrFinish(_ app: AppInfoPresentable, for download: Download) {
		guard AutoSignManager.isEnabled else {
			if isAppInBackground { sendCompletionNotification(for: download, status: "✅ Added to Library") }
			finishImport(of: download, succeeded: true)
			return
		}

		endImport(for: download)
		objectWillChange.send()
		download.isSigning = true

		Task { @MainActor in
			switch await AutoSignManager.shared.sign(app) {
			case .success:
				self.report(for: download, status: "✅ Signed") {
					Toast.success(.localized("Signed successfully"), systemImage: "checkmark.seal.fill")
				}
			case .failure(let error):
				// Keep the import so it can still be signed by hand.
				self.report(for: download, status: "❌ Signing failed") {
					Toast.error(error.localizedDescription, duration: .sticky)
				}
			}

			self.objectWillChange.send()
			download.isSigning = false
			self.finishImport(of: download, succeeded: true)
		}
	}

	private func report(for download: Download, status: String, toast: () -> Void) {
		if isAppInBackground {
			sendCompletionNotification(for: download, status: status)
		} else {
			toast()
		}
	}

	private func finishImport(of download: Download, succeeded: Bool) {
		download.removeStagedFiles()
		download.isActive = false
		endImport(for: download)

		// Drop from activity tracking only once archiving completes (not on download finish).
		if succeeded {
			completedDownloadNames.append(download.fileName)
			allActivityDownloads.removeValue(forKey: download.id)
			finishedDownloadingIDs.remove(download.id)
		}

		// Snapshot before removing this one.
		let isLastDownload = !downloads.contains { other in
			other.id != download.id &&
			(other.isActive || other.isSigning || (other.progress > 0 && other.progress < 1.0) || (other.unpackageProgress > 0 && other.unpackageProgress < 1.0))
		}

		if let index = getDownloadIndex(by: download.id) {
			downloads.remove(at: index)
		}

		guard isLastDownload else { return }

		// Background archiving needs no completion state; foreground keeps it until reopened.
		if isAppInBackground {
			dismissLiveActivityImmediately()
		} else {
			endLiveActivity()
		}
	}
}
