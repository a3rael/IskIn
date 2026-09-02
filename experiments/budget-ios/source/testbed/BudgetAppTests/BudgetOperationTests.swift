import XCTest
@testable import BudgetApp

final class BudgetOperationTests: XCTestCase {
    func testP002PeriodFilterIncludesBoundariesAndExcludesOutsideOperation() throws {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(secondsFromGMT: 0)!
        let periodStart = calendar.date(from: DateComponents(year: 2024, month: 1, day: 1))!
        let periodEnd = calendar.date(from: DateComponents(year: 2024, month: 1, day: 31))!
        let endBoundary = calendar.date(bySettingHour: 23, minute: 59, second: 59, of: periodEnd)!
        let outsidePeriod = calendar.date(byAdding: .day, value: 1, to: periodEnd)!
        let income = try BudgetOperation(
            kind: .income,
            amountKopecks: 100_000,
            category: BudgetOperationValidator.builtInCategories[0],
            date: periodStart
        )
        let expense = try BudgetOperation(
            kind: .expense,
            amountKopecks: 30_000,
            category: BudgetOperationValidator.builtInCategories[1],
            date: endBoundary
        )
        let outside = try BudgetOperation(
            kind: .expense,
            amountKopecks: 20_000,
            category: BudgetOperationValidator.builtInCategories[1],
            date: outsidePeriod
        )

        let filtered = BudgetOperationPeriodFilter.filter(
            [income, expense, outside],
            from: periodStart,
            through: periodEnd,
            calendar: calendar
        )

        XCTAssertEqual(filtered.map(\.id), [income.id, expense.id])
    }

    func testP002TestStoreResetIsolatedFromUserStore() throws {
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent("budget-store-\(UUID().uuidString)")
        defer { try? FileManager.default.removeItem(at: directory) }

        let userStore = BudgetOperationStore(arguments: [], baseDirectory: directory)
        let testStore = BudgetOperationStore(
            arguments: ["--ui-test-mode", "--ui-test-reset"],
            baseDirectory: directory
        )
        let operation = try BudgetOperation(
            kind: .expense,
            amountKopecks: 1_000,
            category: BudgetOperationValidator.builtInCategories[0],
            date: Date(timeIntervalSince1970: 1_700_000_000)
        )

        try userStore.save([operation])
        try testStore.save([operation])
        let resetTestStore = BudgetOperationStore(
            arguments: ["--ui-test-mode", "--ui-test-reset"],
            baseDirectory: directory
        )

        XCTAssertEqual(userStore.load(), [operation])
        XCTAssertEqual(resetTestStore.load(), [])
    }

    func testP003StatisticsCalculateTotalsAndCategoryBreakdownForPeriod() throws {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(secondsFromGMT: 0)!
        let periodStart = calendar.date(from: DateComponents(year: 2024, month: 1, day: 1))!
        let periodEnd = calendar.date(from: DateComponents(year: 2024, month: 1, day: 31))!
        let outsidePeriod = calendar.date(byAdding: .day, value: 1, to: periodEnd)!
        let incomeCategory = BudgetOperationValidator.builtInCategories[0]
        let expenseCategory = BudgetOperationValidator.builtInCategories[1]

        let income = try BudgetOperation(
            kind: .income,
            amountKopecks: 100_000,
            category: incomeCategory,
            date: periodStart
        )
        let expense = try BudgetOperation(
            kind: .expense,
            amountKopecks: 30_000,
            category: expenseCategory,
            date: periodEnd
        )
        let outside = try BudgetOperation(
            kind: .expense,
            amountKopecks: 20_000,
            category: expenseCategory,
            date: outsidePeriod
        )

        let statistics = BudgetStatisticsCalculator.calculate(
            [income, expense, outside],
            from: periodStart,
            through: periodEnd,
            calendar: calendar
        )

        XCTAssertEqual(statistics.incomeKopecks, 100_000)
        XCTAssertEqual(statistics.expenseKopecks, 30_000)
        XCTAssertEqual(statistics.balanceKopecks, 70_000)
        XCTAssertEqual(statistics.incomeByCategory, [incomeCategory: 100_000])
        XCTAssertEqual(statistics.expenseByCategory, [expenseCategory: 30_000])
    }

    func testP004ChangingAndDeletingOperationsRecalculatesStatistics() throws {
        let income = try BudgetOperation(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000001")!,
            kind: .income,
            amountKopecks: 100_000,
            category: BudgetOperationValidator.builtInCategories[0],
            date: Date(timeIntervalSince1970: 1_704_067_200)
        )
        let expense = try BudgetOperation(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000002")!,
            kind: .expense,
            amountKopecks: 30_000,
            category: BudgetOperationValidator.builtInCategories[1],
            date: Date(timeIntervalSince1970: 1_704_067_200)
        )

        let initial = BudgetStatisticsCalculator.calculate([income, expense])
        XCTAssertEqual(initial.incomeKopecks, 100_000)
        XCTAssertEqual(initial.expenseKopecks, 30_000)
        XCTAssertEqual(initial.balanceKopecks, 70_000)

        let changedExpense = try BudgetOperation(
            id: expense.id,
            kind: expense.kind,
            amountKopecks: 40_000,
            category: expense.category,
            date: expense.date
        )
        let afterChange = BudgetStatisticsCalculator.calculate(
            BudgetOperationMutator.replace([income, expense], with: changedExpense)
        )
        XCTAssertEqual(afterChange.incomeKopecks, 100_000)
        XCTAssertEqual(afterChange.expenseKopecks, 40_000)
        XCTAssertEqual(afterChange.balanceKopecks, 60_000)
        XCTAssertEqual(afterChange.expenseByCategory, ["Транспорт": 40_000])

        let afterDelete = BudgetStatisticsCalculator.calculate(
            BudgetOperationMutator.delete([income, changedExpense], id: income.id)
        )
        XCTAssertEqual(afterDelete.incomeKopecks, 0)
        XCTAssertEqual(afterDelete.expenseKopecks, 40_000)
        XCTAssertEqual(afterDelete.balanceKopecks, -40_000)
        XCTAssertEqual(afterDelete.incomeByCategory, [:])
        XCTAssertEqual(afterDelete.expenseByCategory, ["Транспорт": 40_000])
    }

    func testP005StoreRestoresOperationsAndStatisticsAfterRestart() throws {
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent("budget-restart-\(UUID().uuidString)")
        defer { try? FileManager.default.removeItem(at: directory) }

        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(secondsFromGMT: 0)!
        let periodStart = calendar.date(from: DateComponents(year: 2024, month: 1, day: 1))!
        let periodEnd = calendar.date(from: DateComponents(year: 2024, month: 1, day: 31))!
        let outsidePeriod = calendar.date(byAdding: .day, value: 1, to: periodEnd)!
        let income = try BudgetOperation(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000011")!,
            kind: .income,
            amountKopecks: 100_000,
            category: "Продукты",
            date: periodStart
        )
        let expense = try BudgetOperation(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000012")!,
            kind: .expense,
            amountKopecks: 30_000,
            category: "Транспорт",
            date: periodEnd
        )
        let outside = try BudgetOperation(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000013")!,
            kind: .expense,
            amountKopecks: 20_000,
            category: "Транспорт",
            date: outsidePeriod
        )

        let beforeRestart = BudgetOperationStore(arguments: [], baseDirectory: directory)
        try beforeRestart.save([income, expense, outside])
        let afterRestart = BudgetOperationStore(arguments: [], baseDirectory: directory)
        let restored = afterRestart.load()

        XCTAssertEqual(restored, [income, expense, outside])
        let statistics = BudgetStatisticsCalculator.calculate(
            restored,
            from: periodStart,
            through: periodEnd,
            calendar: calendar
        )
        XCTAssertEqual(statistics.incomeKopecks, 100_000)
        XCTAssertEqual(statistics.expenseKopecks, 30_000)
        XCTAssertEqual(statistics.balanceKopecks, 70_000)
        XCTAssertEqual(statistics.incomeByCategory, ["Продукты": 100_000])
        XCTAssertEqual(statistics.expenseByCategory, ["Транспорт": 30_000])
    }
}
