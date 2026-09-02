import Foundation

public enum OperationKind: String, CaseIterable, Codable {
    case income = "Доход"
    case expense = "Расход"
}

public enum BudgetOperationValidationError: Error, Equatable {
    case nonPositiveAmount
    case unsupportedCategory
}

public enum BudgetOperationValidator {
    public static let builtInCategories = [
        "Продукты",
        "Транспорт",
        "Жильё",
        "Здоровье",
        "Другое"
    ]

    public static func validate(
        amountKopecks: Int64,
        category: String
    ) throws {
        guard amountKopecks > 0 else {
            throw BudgetOperationValidationError.nonPositiveAmount
        }
        guard builtInCategories.contains(category) else {
            throw BudgetOperationValidationError.unsupportedCategory
        }
    }

    public static func parseAmountRubles(_ text: String) -> Int64? {
        let normalized = text.trimmingCharacters(in: .whitespacesAndNewlines)
            .replacingOccurrences(of: ",", with: ".")
        guard var decimal = Decimal(string: normalized, locale: Locale(identifier: "en_US_POSIX")), decimal > 0 else {
            return nil
        }

        decimal *= 100
        var rounded = Decimal()
        NSDecimalRound(&rounded, &decimal, 0, .plain)
        let kopecks = NSDecimalNumber(decimal: rounded).int64Value
        return kopecks > 0 ? kopecks : nil
    }
}

public enum BudgetOperationPeriodFilter {
    public static func filter(
        _ operations: [BudgetOperation],
        from startDate: Date,
        through endDate: Date,
        calendar: Calendar = Calendar.current
    ) -> [BudgetOperation] {
        let firstDay = calendar.startOfDay(for: min(startDate, endDate))
        let lastDay = calendar.startOfDay(for: max(startDate, endDate))
        guard let endExclusive = calendar.date(byAdding: .day, value: 1, to: lastDay) else {
            return []
        }

        return operations.filter { operation in
            operation.date >= firstDay && operation.date < endExclusive
        }
    }
}

public struct BudgetStatistics: Equatable {
    public let incomeKopecks: Int64
    public let expenseKopecks: Int64
    public let incomeByCategory: [String: Int64]
    public let expenseByCategory: [String: Int64]

    public var balanceKopecks: Int64 {
        incomeKopecks - expenseKopecks
    }

    public var incomeRublesText: String {
        Self.rublesText(for: incomeKopecks)
    }

    public var expenseRublesText: String {
        Self.rublesText(for: expenseKopecks)
    }

    public var balanceRublesText: String {
        Self.rublesText(for: balanceKopecks)
    }

    public static func rublesText(for kopecks: Int64) -> String {
        String(format: "%.2f ₽", Double(kopecks) / 100.0)
    }
}

public enum BudgetStatisticsCalculator {
    public static func calculate(_ operations: [BudgetOperation]) -> BudgetStatistics {
        var incomeKopecks: Int64 = 0
        var expenseKopecks: Int64 = 0
        var incomeByCategory: [String: Int64] = [:]
        var expenseByCategory: [String: Int64] = [:]

        for operation in operations {
            switch operation.kind {
            case .income:
                incomeKopecks += operation.amountKopecks
                incomeByCategory[operation.category, default: 0] += operation.amountKopecks
            case .expense:
                expenseKopecks += operation.amountKopecks
                expenseByCategory[operation.category, default: 0] += operation.amountKopecks
            }
        }

        return BudgetStatistics(
            incomeKopecks: incomeKopecks,
            expenseKopecks: expenseKopecks,
            incomeByCategory: incomeByCategory,
            expenseByCategory: expenseByCategory
        )
    }

    public static func calculate(
        _ operations: [BudgetOperation],
        from startDate: Date,
        through endDate: Date,
        calendar: Calendar = Calendar.current
    ) -> BudgetStatistics {
        calculate(
            BudgetOperationPeriodFilter.filter(
                operations,
                from: startDate,
                through: endDate,
                calendar: calendar
            )
        )
    }
}

public enum BudgetOperationMutator {
    public static func replace(
        _ operations: [BudgetOperation],
        with replacement: BudgetOperation
    ) -> [BudgetOperation] {
        operations.map { operation in
            operation.id == replacement.id ? replacement : operation
        }
    }

    public static func delete(
        _ operations: [BudgetOperation],
        id: UUID
    ) -> [BudgetOperation] {
        operations.filter { $0.id != id }
    }
}

public struct BudgetOperation: Identifiable, Equatable, Codable {
    public let id: UUID
    public let kind: OperationKind
    public let amountKopecks: Int64
    public let category: String
    public let date: Date

    public init(
        id: UUID = UUID(),
        kind: OperationKind,
        amountKopecks: Int64,
        category: String,
        date: Date
    ) throws {
        try BudgetOperationValidator.validate(amountKopecks: amountKopecks, category: category)
        self.id = id
        self.kind = kind
        self.amountKopecks = amountKopecks
        self.category = category
        self.date = date
    }

    public var amountRublesText: String {
        String(format: "%.2f ₽", Double(amountKopecks) / 100.0)
    }
}
