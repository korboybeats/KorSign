//
//  SettingsDonationCellView.swift
//  KorSign
//
//  Created by samara on 30.04.2025.
//
#if !NIGHTLY && !DEBUG
import SwiftUI
import NimbleViews
import NimbleExtensions

struct SettingsDonationCellView: View {
	var site: String

	var body: some View {
		Section {
			VStack(spacing: 14) {
				Image("KorboyLogo")
					.resizable()
					.scaledToFill()
					.frame(width: 76, height: 76)
					.clipShape(Circle())
					.overlay {
						Circle()
							.stroke(Color.secondary.opacity(0.25), lineWidth: 1)
					}
					.accessibilityLabel("Korboy")
					.padding(.top, 12)

				VStack(spacing: 4) {
					Text("KorSign")
						.font(.title3.bold())
					Text(.localized("A modified version of RyukSign, by Korboy"))
						.font(.subheadline)
						.foregroundStyle(.secondary)
						.multilineTextAlignment(.center)
				}

				Button {
					UIApplication.open(site)
				} label: {
					Text(.localized("Donate to Korboy"))
						.font(.subheadline.weight(.semibold))
						.foregroundStyle(.white)
						.padding(.horizontal, 28)
						.frame(height: 42)
						.background(Color.accentColor, in: Capsule())
				}
				.buttonStyle(.plain)
				.padding(.top, 4)
			}
			.frame(maxWidth: .infinity)
			.padding(.vertical, 8)
		}
	}
}
#endif
