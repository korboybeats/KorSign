import SwiftUI

/// A persistent presentation anchor lets SwiftUI serialize dismissal and reopening.
struct DownloadOverlaySheetWrapper: View {
    @ObservedObject var downloadManager: DownloadManager
    @Binding var isPresented: Bool
    @AppStorage("Feather.dynamicOverlaySize") private var dynamicOverlaySize = true

    private var height: CGFloat {
        let count = downloadManager.downloads.filter {
            $0.isActive || $0.progress > 0 || $0.unpackageProgress > 0
        }.count
        guard dynamicOverlaySize else { return min(800, UIScreen.main.bounds.height - 150) }
        return count == 0 ? 280 : min(160 + CGFloat(count) * 110, 800)
    }

    var body: some View {
        Color.clear
            .frame(width: 0, height: 0)
            .allowsHitTesting(false)
            .sheet(isPresented: $isPresented) {
                DownloadOverlaySheetContent(downloadManager: downloadManager, isPresented: $isPresented)
                    .presentationDetents([.height(height)])
                    .presentationDragIndicator(.hidden)
            }
    }
}
