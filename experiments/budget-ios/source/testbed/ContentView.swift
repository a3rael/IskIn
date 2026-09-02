import SwiftUI

struct ContentView: View {
    private enum HistoryFilter: String, CaseIterable {
        case all = "Все"
        case selectedPeriod = "Выбранный период"
    }

    private let store: BudgetOperationStore

    @State private var kind: OperationKind = .expense
    @State private var amountText = ""
    @State private var category = BudgetOperationValidator.builtInCategories[0]
    @State private var date = Date()
    @State private var operations: [BudgetOperation] = []
    @State private var validationMessage: String?
    @State private var historyFilter: HistoryFilter = .all
    @State private var periodStart = Calendar.current.date(byAdding: .day, value: -30, to: Date()) ?? Date()
    @State private var periodEnd = Date()
    @State private var editingOperationID: UUID? = nil

    init(store: BudgetOperationStore = BudgetOperationStore()) {
        self.store = store
        _operations = State(initialValue: store.load())
    }

    private var displayedOperations: [BudgetOperation] {
        guard historyFilter == .selectedPeriod else {
            return operations
        }

        return BudgetOperationPeriodFilter.filter(
            operations,
            from: periodStart,
            through: periodEnd
        )
    }

    private var displayedStatistics: BudgetStatistics {
        BudgetStatisticsCalculator.calculate(displayedOperations)
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Новая операция") {
                    Picker("Тип", selection: $kind) {
                        ForEach(OperationKind.allCases, id: \.self) { item in
                            Text(item.rawValue).tag(item)
                        }
                    }
                    .pickerStyle(.segmented)
                    .accessibilityIdentifier("budget.operation.type")

                    TextField("Сумма в рублях", text: $amountText)
                        .keyboardType(.decimalPad)
                        .accessibilityIdentifier("budget.operation.amount")

                    Picker("Категория", selection: $category) {
                        ForEach(BudgetOperationValidator.builtInCategories, id: \.self) { item in
                            Text(item).tag(item)
                        }
                    }
                    .accessibilityIdentifier("budget.operation.category")

                    DatePicker("Дата", selection: $date, displayedComponents: .date)
                        .accessibilityIdentifier("budget.operation.date")

                    Button(editingOperationID == nil ? "Добавить" : "Сохранить изменения") {
                        addOperation()
                    }
                    .buttonStyle(.borderedProminent)
                    .accessibilityIdentifier("budget.operation.add")

                    if let validationMessage {
                        Text(validationMessage)
                            .foregroundStyle(.red)
                    }
                }

                Section("Период истории") {
                    Picker("Показать", selection: $historyFilter) {
                        ForEach(HistoryFilter.allCases, id: \.self) { filter in
                            Text(filter.rawValue).tag(filter)
                        }
                    }
                    .pickerStyle(.segmented)
                    .accessibilityIdentifier("budget.history.filter")

                    if historyFilter == .selectedPeriod {
                        DatePicker("Начало", selection: $periodStart, displayedComponents: .date)
                            .accessibilityIdentifier("budget.history.start")
                        DatePicker("Конец", selection: $periodEnd, displayedComponents: .date)
                            .accessibilityIdentifier("budget.history.end")
                    }
                }

                Section("Статистика") {
                    LabeledContent("Доходы", value: displayedStatistics.incomeRublesText)
                        .accessibilityIdentifier("budget.statistics.income")
                    LabeledContent("Расходы", value: displayedStatistics.expenseRublesText)
                        .accessibilityIdentifier("budget.statistics.expense")
                    LabeledContent("Разница", value: displayedStatistics.balanceRublesText)
                        .accessibilityIdentifier("budget.statistics.balance")

                    if !displayedStatistics.incomeByCategory.isEmpty {
                        Text("Доходы по категориям")
                            .font(.subheadline)
                        ForEach(displayedStatistics.incomeByCategory.keys.sorted(), id: \.self) { category in
                            LabeledContent(
                                category,
                                value: BudgetStatistics.rublesText(
                                    for: displayedStatistics.incomeByCategory[category] ?? 0
                                )
                            )
                            .accessibilityIdentifier("budget.statistics.income-category.\(category)")
                        }
                    }

                    if !displayedStatistics.expenseByCategory.isEmpty {
                        Text("Расходы по категориям")
                            .font(.subheadline)
                        ForEach(displayedStatistics.expenseByCategory.keys.sorted(), id: \.self) { category in
                            LabeledContent(
                                category,
                                value: BudgetStatistics.rublesText(
                                    for: displayedStatistics.expenseByCategory[category] ?? 0
                                )
                            )
                            .accessibilityIdentifier("budget.statistics.expense-category.\(category)")
                        }
                    }
                }

                Section("Операции") {
                    if displayedOperations.isEmpty {
                        Text(historyFilter == .all ? "Операций пока нет" : "За выбранный период операций нет")
                            .foregroundStyle(.secondary)
                    } else {
                        ForEach(displayedOperations) { operation in
                            HStack {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(operation.kind.rawValue)
                                        .font(.headline)
                                    Text(operation.category)
                                        .font(.subheadline)
                                        .foregroundStyle(.secondary)
                                    Text(operation.date, format: .dateTime.year().month().day())
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                                Spacer()
                                Text(operation.amountRublesText)
                                    .foregroundStyle(operation.kind == .income ? .green : .primary)
                                    .accessibilityIdentifier("budget.operation.amount.\(operation.amountRublesText)")
                                Button("Изменить") {
                                    editingOperationID = operation.id
                                    kind = operation.kind
                                    amountText = operation.amountRublesText.replacingOccurrences(of: " ₽", with: "")
                                    category = operation.category
                                    date = operation.date
                                    validationMessage = nil
                                }
                                .buttonStyle(.bordered)
                                .accessibilityIdentifier("budget.operation.edit.\(operation.amountRublesText)")
                                Button("Удалить") {
                                    deleteOperation(operation)
                                }
                                .buttonStyle(.bordered)
                                .accessibilityIdentifier("budget.operation.delete.\(operation.amountRublesText)")
                            }
                        }
                    }
                }
            }
            .navigationTitle("Budget MVP")
        }
    }

    private func addOperation() {
        guard let amountKopecks = BudgetOperationValidator.parseAmountRubles(amountText) else {
            validationMessage = "Введите положительную сумму в рублях"
            return
        }

        do {
            let operation = try BudgetOperation(
                id: editingOperationID ?? UUID(),
                kind: kind,
                amountKopecks: amountKopecks,
                category: category,
                date: date
            )
            if let editingOperationID {
                operations = BudgetOperationMutator.replace(operations, with: operation)
                self.editingOperationID = nil
            } else {
                operations.insert(operation, at: 0)
            }
            try? store.save(operations)
            amountText = ""
            validationMessage = nil
        } catch BudgetOperationValidationError.nonPositiveAmount {
            validationMessage = "Введите положительную сумму в рублях"
        } catch BudgetOperationValidationError.unsupportedCategory {
            validationMessage = "Выберите встроенную категорию"
        } catch {
            validationMessage = "Не удалось создать операцию"
        }
    }

    private func deleteOperation(_ operation: BudgetOperation) {
        operations = BudgetOperationMutator.delete(operations, id: operation.id)
        if editingOperationID == operation.id {
            editingOperationID = nil
            amountText = ""
        }
        try? store.save(operations)
    }
}

#Preview {
    ContentView()
}
