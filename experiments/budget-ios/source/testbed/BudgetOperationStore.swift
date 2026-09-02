import Foundation

struct BudgetOperationStore {
    private static let uiTestModeArgument = "--ui-test-mode"
    private static let uiTestResetArgument = "--ui-test-reset"
    static let p0TestFixtureArgument = "--ui-test-fixture-p0-02"

    private let fileManager: FileManager
    private let fileURL: URL
    private let now: Date

    init(
        arguments: [String] = ProcessInfo.processInfo.arguments,
        fileManager: FileManager = .default,
        baseDirectory: URL? = nil,
        now: Date = Date()
    ) {
        self.fileManager = fileManager
        self.now = now

        let isUITestMode = arguments.contains(Self.uiTestModeArgument)
        let directory = baseDirectory ?? fileManager.urls(
            for: .applicationSupportDirectory,
            in: .userDomainMask
        ).first ?? fileManager.temporaryDirectory
        let fileName = isUITestMode ? "ui-test-operations.json" : "operations.json"
        self.fileURL = directory.appendingPathComponent(fileName)

        if isUITestMode && arguments.contains(Self.uiTestResetArgument) {
            try? fileManager.removeItem(at: fileURL)
        }

        if isUITestMode && arguments.contains(Self.p0TestFixtureArgument) && load().isEmpty {
            seedP0TestFixture()
        }
    }

    func load() -> [BudgetOperation] {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        guard let data = try? Data(contentsOf: fileURL),
              let operations = try? decoder.decode([BudgetOperation].self, from: data) else {
            return []
        }
        return operations
    }

    func save(_ operations: [BudgetOperation]) throws {
        try fileManager.createDirectory(
            at: fileURL.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        let data = try encoder.encode(operations)
        try data.write(to: fileURL, options: .atomic)
    }

    private func seedP0TestFixture() {
        let calendar = Calendar.current
        let recentA = calendar.date(byAdding: .day, value: -2, to: now) ?? now
        let recentB = calendar.date(byAdding: .day, value: -1, to: now) ?? now
        let outsidePeriodC = calendar.date(byAdding: .day, value: -40, to: now) ?? now

        guard let operations = try? [
            BudgetOperation(
                kind: .income,
                amountKopecks: 100_000,
                category: BudgetOperationValidator.builtInCategories[0],
                date: recentA
            ),
            BudgetOperation(
                kind: .expense,
                amountKopecks: 30_000,
                category: BudgetOperationValidator.builtInCategories[1],
                date: recentB
            ),
            BudgetOperation(
                kind: .expense,
                amountKopecks: 20_000,
                category: BudgetOperationValidator.builtInCategories[1],
                date: outsidePeriodC
            )
        ] else {
            return
        }

        try? save(operations)
    }
}
