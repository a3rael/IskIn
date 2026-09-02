import XCTest

final class BudgetAppUITests: XCTestCase {
    private let app = XCUIApplication()

    override func setUpWithError() throws {
        continueAfterFailure = false
        app.launchArguments = [
            "--ui-test-mode",
            "--ui-test-reset",
            "--ui-test-fixture-p0-02"
        ]
        app.terminate()
        app.launch()
        XCTAssertTrue(app.wait(for: .runningForeground, timeout: 10))
    }

    func testP002HistoryAndSelectedPeriodAreReviewable() throws {
        let allAmount = app.staticTexts["budget.operation.amount.1000.00 ₽"]
        let includedAmount = app.staticTexts["budget.operation.amount.300.00 ₽"]
        let excludedAmount = app.staticTexts["budget.operation.amount.200.00 ₽"]
        app.swipeUp()
        app.swipeUp()
        XCTAssertTrue(allAmount.waitForExistence(timeout: 10))
        XCTAssertTrue(includedAmount.exists)
        app.swipeUp()
        XCTAssertTrue(excludedAmount.waitForExistence(timeout: 10))
        attachScreenshot(named: "p0-02-all-operations")

        app.swipeDown()
        app.swipeDown()
        app.swipeDown()
        let selectedPeriod = app.buttons["Выбранный период"]
        XCTAssertTrue(selectedPeriod.waitForExistence(timeout: 5))
        selectedPeriod.tap()
        app.swipeUp()
        XCTAssertTrue(allAmount.waitForExistence(timeout: 5))
        XCTAssertTrue(includedAmount.exists)
        XCTAssertFalse(excludedAmount.exists)
        attachScreenshot(named: "p0-02-selected-period")

        app.swipeDown()
        app.swipeDown()
        app.swipeDown()
        let allPeriods = app.buttons["Все"]
        XCTAssertTrue(allPeriods.waitForExistence(timeout: 5))
        allPeriods.tap()
        app.swipeUp()
        app.swipeUp()
        app.swipeUp()
        XCTAssertTrue(excludedAmount.waitForExistence(timeout: 5))
        attachScreenshot(named: "p0-02-period-changed")
    }

    func testP003SelectedPeriodShowsTotalsAndCategoryBreakdown() throws {
        let selectedPeriod = app.buttons["Выбранный период"]
        XCTAssertTrue(selectedPeriod.waitForExistence(timeout: 10))
        selectedPeriod.tap()
        app.swipeUp()

        let income = app.staticTexts["budget.statistics.income"]
        let expense = app.staticTexts["budget.statistics.expense"]
        let balance = app.staticTexts["budget.statistics.balance"]
        XCTAssertTrue(income.waitForExistence(timeout: 5))
        XCTAssertEqual(income.label, "Доходы, 1000.00 ₽")
        XCTAssertEqual(expense.label, "Расходы, 300.00 ₽")
        XCTAssertEqual(balance.label, "Разница, 700.00 ₽")
        XCTAssertTrue(app.staticTexts["budget.statistics.income-category.Продукты"].exists)
        XCTAssertTrue(app.staticTexts["budget.statistics.expense-category.Транспорт"].exists)
        attachScreenshot(named: "p0-03-selected-period-statistics")
    }

    func testP004ChangingAndDeletingRecalculatesSelectedPeriodStatistics() throws {
        let selectedPeriod = app.buttons["Выбранный период"]
        XCTAssertTrue(selectedPeriod.waitForExistence(timeout: 10))
        selectedPeriod.tap()
        app.swipeUp()

        let income = app.staticTexts["budget.statistics.income"]
        let expense = app.staticTexts["budget.statistics.expense"]
        let balance = app.staticTexts["budget.statistics.balance"]
        XCTAssertEqual(income.label, "Доходы, 1000.00 ₽")
        XCTAssertEqual(expense.label, "Расходы, 300.00 ₽")
        XCTAssertEqual(balance.label, "Разница, 700.00 ₽")
        XCTAssertTrue(app.staticTexts["budget.statistics.income-category.Продукты"].exists)
        XCTAssertTrue(app.staticTexts["budget.statistics.expense-category.Транспорт"].exists)
        attachScreenshot(named: "p0-04-initial-statistics")

        app.swipeUp()
        let editExpense = app.buttons["budget.operation.edit.300.00 ₽"]
        XCTAssertTrue(editExpense.waitForExistence(timeout: 10))
        editExpense.tap()

        app.swipeDown()
        app.swipeDown()
        app.swipeDown()
        let amount = app.textFields["budget.operation.amount"]
        let saveChanges = app.buttons["Сохранить изменения"]
        XCTAssertTrue(saveChanges.waitForExistence(timeout: 5))
        amount.tap(withNumberOfTaps: 3, numberOfTouches: 1)
        amount.typeText("400")
        saveChanges.tap()
        app.swipeUp()

        XCTAssertEqual(income.label, "Доходы, 1000.00 ₽")
        XCTAssertEqual(expense.label, "Расходы, 400.00 ₽")
        XCTAssertEqual(balance.label, "Разница, 600.00 ₽")
        XCTAssertTrue(app.staticTexts["budget.operation.amount.400.00 ₽"].exists)
        XCTAssertFalse(app.staticTexts["budget.operation.amount.300.00 ₽"].exists)
        XCTAssertTrue(app.staticTexts["budget.statistics.expense-category.Транспорт"].exists)
        attachScreenshot(named: "p0-04-after-change")

        app.swipeUp()
        let deleteIncome = app.buttons["budget.operation.delete.1000.00 ₽"]
        XCTAssertTrue(deleteIncome.waitForExistence(timeout: 10))
        deleteIncome.tap()
        app.swipeUp()

        XCTAssertEqual(income.label, "Доходы, 0.00 ₽")
        XCTAssertEqual(expense.label, "Расходы, 400.00 ₽")
        XCTAssertEqual(balance.label, "Разница, -400.00 ₽")
        XCTAssertFalse(app.staticTexts["budget.operation.amount.1000.00 ₽"].exists)
        XCTAssertTrue(app.staticTexts["budget.operation.amount.400.00 ₽"].exists)
        XCTAssertFalse(app.staticTexts["budget.statistics.income-category.Продукты"].exists)
        XCTAssertTrue(app.staticTexts["budget.statistics.expense-category.Транспорт"].exists)
        attachScreenshot(named: "p0-04-after-delete")
    }

    func testP005OperationsAndStatisticsSurviveApplicationRestart() throws {
        let allIncome = app.staticTexts["budget.operation.amount.1000.00 ₽"]
        let allExpense = app.staticTexts["budget.operation.amount.300.00 ₽"]
        let outsideExpense = app.staticTexts["budget.operation.amount.200.00 ₽"]
        app.swipeUp()
        app.swipeUp()
        XCTAssertTrue(allIncome.waitForExistence(timeout: 10))
        XCTAssertTrue(allExpense.exists)
        XCTAssertTrue(outsideExpense.exists)

        app.terminate()
        app.launchArguments = ["--ui-test-mode", "--ui-test-fixture-p0-02"]
        app.launch()
        XCTAssertTrue(app.wait(for: .runningForeground, timeout: 10))

        app.swipeUp()
        app.swipeUp()
        XCTAssertTrue(allIncome.waitForExistence(timeout: 10))
        XCTAssertTrue(allExpense.exists)
        XCTAssertTrue(outsideExpense.exists)

        let selectedPeriod = app.buttons["Выбранный период"]
        XCTAssertTrue(selectedPeriod.waitForExistence(timeout: 10))
        selectedPeriod.tap()
        app.swipeUp()
        let income = app.staticTexts["budget.statistics.income"]
        let expense = app.staticTexts["budget.statistics.expense"]
        let balance = app.staticTexts["budget.statistics.balance"]
        XCTAssertEqual(income.label, "Доходы, 1000.00 ₽")
        XCTAssertEqual(expense.label, "Расходы, 300.00 ₽")
        XCTAssertEqual(balance.label, "Разница, 700.00 ₽")
        XCTAssertTrue(app.staticTexts["budget.statistics.income-category.Продукты"].exists)
        XCTAssertTrue(app.staticTexts["budget.statistics.expense-category.Транспорт"].exists)
        attachScreenshot(named: "p0-05-after-restart")
    }

    private func attachScreenshot(named name: String) {
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}
