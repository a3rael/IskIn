import SwiftUI

@main
struct BudgetAppApp: App {
    private let operationStore: BudgetOperationStore

    init() {
        operationStore = BudgetOperationStore(arguments: ProcessInfo.processInfo.arguments)
    }

    var body: some Scene {
        WindowGroup {
            ContentView(store: operationStore)
        }
    }
}
