import Foundation

@main
struct BudgetCoreChecks {
    static func main() throws {
        let testDate = Date(timeIntervalSince1970: 1_700_000_000)
        let income = try BudgetOperation(
            kind: .income,
            amountKopecks: 100_000,
            category: BudgetOperationValidator.builtInCategories[0],
            date: testDate
        )
        let expense = try BudgetOperation(
            kind: .expense,
            amountKopecks: 30_000,
            category: BudgetOperationValidator.builtInCategories[1],
            date: testDate
        )

        precondition(income.kind == .income)
        precondition(expense.kind == .expense)
        precondition(income.amountRublesText == "1000.00 ₽")
        precondition(expense.amountRublesText == "300.00 ₽")
        precondition(BudgetOperationValidator.parseAmountRubles("1000") == 100_000)
        precondition(BudgetOperationValidator.parseAmountRubles("300,00") == 30_000)
        precondition(BudgetOperationValidator.parseAmountRubles("0") == nil)
        precondition(BudgetOperationValidator.parseAmountRubles("-1") == nil)
        precondition(BudgetOperationValidator.parseAmountRubles("abc") == nil)

        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(secondsFromGMT: 0)!
        let periodStart = calendar.date(from: DateComponents(year: 2024, month: 1, day: 1))!
        let periodEnd = calendar.date(from: DateComponents(year: 2024, month: 1, day: 31))!
        let endBoundary = calendar.date(bySettingHour: 23, minute: 59, second: 59, of: periodEnd)!
        let outsidePeriod = calendar.date(byAdding: .day, value: 1, to: periodEnd)!
        let periodIncome = try BudgetOperation(
            kind: .income,
            amountKopecks: 100_000,
            category: BudgetOperationValidator.builtInCategories[0],
            date: periodStart
        )
        let periodExpense = try BudgetOperation(
            kind: .expense,
            amountKopecks: 30_000,
            category: BudgetOperationValidator.builtInCategories[1],
            date: endBoundary
        )
        let outsideOperation = try BudgetOperation(
            kind: .expense,
            amountKopecks: 20_000,
            category: BudgetOperationValidator.builtInCategories[1],
            date: outsidePeriod
        )
        let allOperations = [periodIncome, periodExpense, outsideOperation]
        let filteredOperations = BudgetOperationPeriodFilter.filter(
            allOperations,
            from: periodStart,
            through: periodEnd,
            calendar: calendar
        )
        precondition(filteredOperations.map(\.id) == [periodIncome.id, periodExpense.id])

        let narrowedOperations = BudgetOperationPeriodFilter.filter(
            allOperations,
            from: periodEnd,
            through: periodEnd,
            calendar: calendar
        )
        precondition(narrowedOperations.map(\.id) == [periodExpense.id])

        do {
            _ = try BudgetOperation(
                kind: .expense,
                amountKopecks: 0,
                category: BudgetOperationValidator.builtInCategories[0],
                date: testDate
            )
            preconditionFailure("zero amount must be rejected")
        } catch BudgetOperationValidationError.nonPositiveAmount {
            // Expected.
        }

        do {
            _ = try BudgetOperation(
                kind: .expense,
                amountKopecks: 100,
                category: "Пользовательская категория",
                date: testDate
            )
            preconditionFailure("unsupported category must be rejected")
        } catch BudgetOperationValidationError.unsupportedCategory {
            // Expected.
        }

        print("PASS G2: income and expense creation")
        print("PASS G2: positive RUB amount validation")
        print("PASS G2: fixed built-in category validation")
        print("PASS G2: operation date is retained")
        print("PASS G3: period includes both date boundaries")
        print("PASS G3: operation outside period is excluded")
        print("PASS G3: changing period changes history")
    }
}
