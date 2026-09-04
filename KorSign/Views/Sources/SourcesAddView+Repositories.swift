//
//  SourcesAddView+Repositories.swift
//  KorSign
//

import SwiftUI
import NimbleViews
import AltSourceKit
import OSLog

extension SourcesAddView {
	// MARK: - Fetch Community Repository List
	func _fetchCommunityRepositoriesList() async {
		await MainActor.run {
			communityReposFetchError = nil
		}

		do {
			let (data, response) = try await URLSession.shared.data(from: RepositorySettings.communityListURL)

			guard let httpResponse = response as? HTTPURLResponse,
				httpResponse.statusCode == 200 else {
				await MainActor.run {
					communityReposFetchError = "Failed to fetch repository list. Server returned an error."
					Logger.misc.error("Failed to fetch community repositories: Invalid response")
				}
				return
			}

			let raw = try JSONSerialization.jsonObject(with: data, options: [])

			guard let strings = raw as? [String] else {
				await MainActor.run {
					communityReposFetchError = "Unexpected JSON format in repos.json"
				}
				return
			}

			let urls = strings.compactMap { URL(string: $0) }

			await MainActor.run {
				communityRepos = urls
				communityReposCount = urls.count
				communityReposFetchError = nil
				Logger.misc.info("Successfully fetched \(urls.count) community repositories")
			}

		} catch {
			await MainActor.run {
				if (error as NSError).code == NSURLErrorNotConnectedToInternet ||
					(error as NSError).code == NSURLErrorTimedOut ||
					(error as NSError).code == NSURLErrorNetworkConnectionLost {
					communityReposFetchError = "No internet connection. Please check your network and try again."
				} else {
					communityReposFetchError = "Failed to load repositories: \(error.localizedDescription)"
				}
				communityReposCount = 0
				Logger.misc.error("Failed to fetch community repositories: \(error.localizedDescription)")
			}
		}
	}

	// MARK: - Community Repository Handler
	func _addCommunityRepositories() {
		guard !communityRepos.isEmpty else {
			_isAddingCommunityRepos = false
			Toast.error("No community repositories available", duration: .sticky)
			return
		}

		Task {
			let fetched = await FR.fetchRepositories(from: communityRepos)
			let dict = Dictionary(fetched, uniquingKeysWith: { first, _ in first })

			await MainActor.run {
				if dict.isEmpty {
					_isAddingCommunityRepos = false
					Toast.error("Failed to fetch repository data. Please check your connection and try again.", duration: .sticky)
				} else {
					Storage.shared.addSources(repos: dict) { _ in
						Toast.success("Successfully added \(dict.count) community repositories")
						_isAddingCommunityRepos = false
						_refreshFilteredRecommendedSourcesData()
						dismiss()
					}
				}
			}
		}
	}

	func _fetchRecommendedRepositories() async {
		let fetched = await FR.fetchRepositories(from: recommendedSources)
		await MainActor.run {
			recommendedSourcesData = fetched
			_refreshFilteredRecommendedSourcesData()
		}
	}

	func _fetchImportedRepositories(
		_ code: String?,
		competion: @escaping (Bool, Int) -> Void
	) {
		guard let code else {
			competion(false, 0)
			return
		}

		let handler = ASDeobfuscator(with: code)
		let repoUrls = handler.decode().compactMap { URL(string: $0) }
		guard !repoUrls.isEmpty else {
			competion(false, 0)
			return
		}

		Task {
			let fetched = await FR.fetchRepositories(from: repoUrls)

			let dict = Dictionary(fetched, uniquingKeysWith: { first, _ in first })

			await MainActor.run {
				if dict.isEmpty {
					competion(false, 0)
				} else {
					Storage.shared.addSources(repos: dict) { _ in
						competion(true, dict.count)
					}
				}
			}
		}
	}

}
