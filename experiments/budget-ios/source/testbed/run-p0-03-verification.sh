#!/bin/bash
# Canonical local proof for P0-03 (G1 + G4).
set -u -o pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROJECT="$ROOT/testbeds/budget-ios/BudgetApp.xcodeproj"
EVIDENCE_ROOT="$ROOT/testbeds/budget-ios/evidence"
RUN_ID="$(date -u '+%Y%m%dT%H%M%SZ')-$$"
RUN_DIR="$EVIDENCE_ROOT/runs/$RUN_ID"
MANIFEST="$RUN_DIR/manifest.json"
REPORT="$RUN_DIR/report.md"
PROOF_RECORD="$RUN_DIR/proof-record.json"
WORK="${TMPDIR:-/tmp}/agent-native-pdlc-p0-03"
DERIVED_DATA="$WORK/DerivedData"
TEST_RESULT_BUNDLE="$RUN_DIR/BudgetApp-P0-03.xcresult"
TEST_LOG="$WORK/xcodebuild-test.log"
XCRESULT_FILES_MANIFEST="$RUN_DIR/BudgetApp-P0-03.xcresult.files.sha256"
ATTACHMENTS_DIR="$WORK/xcresult-attachments"
ATTACHMENT_EXPORT_LOG="$WORK/xcresult-attachments.log"

rm -rf "$WORK"
mkdir -p "$WORK" "$EVIDENCE_ROOT/runs"
START="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
COMMIT="$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || printf 'unknown')"
XCODE_VERSION="$(xcodebuild -version 2>/dev/null | tr '\n' ' ' || printf 'unavailable')"
SWIFT_VERSION="$(swiftc --version 2>/dev/null | tr '\n' ' ' || printf 'unavailable')"

DEVICE_JSON="$(xcrun simctl list devices available --json 2>/dev/null || printf '{}')"
DEVICE_ID="$(printf '%s' "$DEVICE_JSON" | python3 -c '
import json, sys
for devices in json.load(sys.stdin).get("devices", {}).values():
    for device in devices:
        if device.get("isAvailable") and device.get("state") == "Booted":
            print(device["udid"]); raise SystemExit
for devices in json.load(sys.stdin).get("devices", {}).values():
    for device in devices:
        if device.get("isAvailable") and device.get("name") == "iPhone 17 Pro":
            print(device["udid"]); raise SystemExit
raise SystemExit(1)
' 2>/dev/null || printf 'unavailable')"
DEVICE_NAME="$(printf '%s' "$DEVICE_JSON" | python3 -c '
import json, sys
data = json.load(sys.stdin)
udid = sys.argv[1]
for devices in data.get("devices", {}).values():
    for device in devices:
        if device.get("udid") == udid:
            print(device.get("name", "unknown")); raise SystemExit
print("unavailable")
' "$DEVICE_ID")"

if ! mkdir "$RUN_DIR"; then
  printf '%s\n' "Refusing to reuse run directory: $RUN_DIR" >&2
  exit 1
fi

python3 - "$MANIFEST" "$ROOT" "$RUN_ID" "$START" "$COMMIT" "$XCODE_VERSION" "$SWIFT_VERSION" "$DEVICE_ID" <<'PY'
import hashlib, json, sys
from pathlib import Path
manifest_path = Path(sys.argv[1])
root = Path(sys.argv[2])
run_id, started, commit, xcode, swift, simulator_udid = sys.argv[3:]
g1_paths = [
    "testbeds/budget-ios/run-p0-03-verification.sh",
    "testbeds/budget-ios/BudgetApp.xcodeproj/project.pbxproj",
    "testbeds/budget-ios/BudgetAppApp.swift",
    "testbeds/budget-ios/ContentView.swift",
    "testbeds/budget-ios/BudgetOperation.swift",
    "testbeds/budget-ios/BudgetOperationStore.swift",
    "testbeds/budget-ios/BudgetAppUITests/BudgetAppUITests.swift",
    "testbeds/budget-ios/BudgetApp.xcodeproj/xcshareddata/xcschemes/BudgetApp.xcscheme",
]
g4_paths = [
    "testbeds/budget-ios/run-p0-03-verification.sh",
    "testbeds/budget-ios/BudgetOperation.swift",
    "testbeds/budget-ios/ContentView.swift",
    "testbeds/budget-ios/BudgetOperationStore.swift",
    "testbeds/budget-ios/BudgetAppTests/BudgetOperationTests.swift",
    "testbeds/budget-ios/BudgetAppUITests/BudgetAppUITests.swift",
    "testbeds/budget-ios/BudgetApp.xcodeproj/project.pbxproj",
]
def entry(path):
    absolute = root / path
    return {"path": path, "sha256": hashlib.sha256(absolute.read_bytes()).hexdigest()}
payload = {
    "schema_version": 1, "run_id": run_id, "outcome": "P0-03",
    "created_at_utc": started,
    "canonical_command": "./testbeds/budget-ios/run-p0-03-verification.sh",
    "repository_runner": "testbeds/budget-ios/run-p0-03-verification.sh",
    "runner_sha256": entry(g1_paths[0])["sha256"],
    "environment": {"xcodebuild": xcode, "swiftc": swift, "target": "iOS Simulator", "simulator_udid": simulator_udid},
    "scopes": {"G1": {"inputs": [entry(path) for path in g1_paths]}, "G4": {"inputs": [entry(path) for path in g4_paths]}},
}
temporary = manifest_path.with_suffix(".json.tmp")
temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
temporary.replace(manifest_path)
PY

if [ "$DEVICE_ID" != "unavailable" ]; then
  DESTINATION="platform=iOS Simulator,id=$DEVICE_ID"
else
  DESTINATION="platform=iOS Simulator,name=iPhone 17 Pro"
fi

TEST_START_EPOCH="$(date +%s)"
xcodebuild -project "$PROJECT" -scheme BudgetApp -destination "$DESTINATION" \
  -derivedDataPath "$DERIVED_DATA" -resultBundlePath "$TEST_RESULT_BUNDLE" \
  -only-testing:BudgetAppTests/BudgetOperationTests/testP003StatisticsCalculateTotalsAndCategoryBreakdownForPeriod \
  -only-testing:BudgetAppUITests/BudgetAppUITests/testP003SelectedPeriodShowsTotalsAndCategoryBreakdown \
  test >"$TEST_LOG" 2>&1
TEST_STATUS=$?
TEST_DURATION_SECONDS=$(( $(date +%s) - TEST_START_EPOCH ))

ATTACHMENT_EXPORT_STATUS=1
SCREENSHOT_COUNT=0
if [ -d "$TEST_RESULT_BUNDLE" ]; then
  rm -rf "$ATTACHMENTS_DIR"
  mkdir -p "$ATTACHMENTS_DIR"
  xcrun xcresulttool export attachments --path "$TEST_RESULT_BUNDLE" --output-path "$ATTACHMENTS_DIR" >"$ATTACHMENT_EXPORT_LOG" 2>&1
  ATTACHMENT_EXPORT_STATUS=$?
  if [ "$ATTACHMENT_EXPORT_STATUS" -eq 0 ]; then
    SCREENSHOT_COUNT="$(python3 - "$ATTACHMENTS_DIR" <<'PY'
import sys
from pathlib import Path
root = Path(sys.argv[1])
print(sum(1 for path in root.rglob("*") if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}))
PY
    )"
  fi
fi

XCRESULT_DIGEST="unavailable"
if [ -d "$TEST_RESULT_BUNDLE" ]; then
  XCRESULT_DIGEST="$(python3 - "$TEST_RESULT_BUNDLE" "$XCRESULT_FILES_MANIFEST" <<'PY'
import hashlib, json, sys
from pathlib import Path
bundle, manifest = Path(sys.argv[1]), Path(sys.argv[2])
entries = [{"path": p.relative_to(bundle).as_posix(), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted((x for x in bundle.rglob("*") if x.is_file()), key=lambda x: x.relative_to(bundle).as_posix())]
digest = hashlib.sha256("".join(f"{e['path']}\t{e['sha256']}\n" for e in entries).encode()).hexdigest()
temporary = manifest.with_suffix(".tmp")
temporary.write_text(json.dumps({"schema_version": 1, "result_bundle": bundle.name, "files": entries, "digest_sha256": digest}, indent=2) + "\n")
temporary.replace(manifest)
print(digest)
PY
  )"
fi

G1_STATUS="FAIL"
[ "$TEST_STATUS" -eq 0 ] && [ -d "$TEST_RESULT_BUNDLE" ] && G1_STATUS="PASS"
G4_STATUS="FAIL"
[ "$TEST_STATUS" -eq 0 ] && [ "$SCREENSHOT_COUNT" -ge 1 ] && G4_STATUS="PASS"
OVERALL_STATUS="FAIL"
[ "$G1_STATUS" = "PASS" ] && [ "$G4_STATUS" = "PASS" ] && OVERALL_STATUS="PASS"

{
  printf '%s\n' '# P0-03 automatic verification' '' 'report_version: 1' "run_id: $RUN_ID" 'Generated by: `./testbeds/budget-ios/run-p0-03-verification.sh`' "Started (UTC): $START" "Repository commit: $COMMIT" "Environment: $XCODE_VERSION; $SWIFT_VERSION" "Simulator: $DEVICE_NAME ($DEVICE_ID)" ''
  printf '%s\n' '## Contract' '' '- Canonical command: `./testbeds/budget-ios/run-p0-03-verification.sh`' '- Repository runner: `testbeds/budget-ios/run-p0-03-verification.sh`' "- Manifest: $MANIFEST" "- Versioned report: $REPORT" "- Versioned proof-record: $PROOF_RECORD" "- Xcode result bundle: $TEST_RESULT_BUNDLE" "- .xcresult files manifest: $XCRESULT_FILES_MANIFEST" "- .xcresult digest: $XCRESULT_DIGEST" ''
  printf '%s\n' '## G1 — сборка и запуск в iOS Simulator' '' '- gate_id: G1' '- criterion: приложение собирается и запускается в iOS Simulator' '- expected: selected P0-03 tests complete and create result bundle' "- observed: xcodebuild_test=$TEST_STATUS, result_bundle=$(if [ -d "$TEST_RESULT_BUNDLE" ]; then printf 'present'; else printf 'missing'; fi)" "- run_status: $G1_STATUS" ''
  printf '%s\n' '## G4 — статистика за период и по категориям' '' '- gate_id: G4' '- criterion: selected period shows income, expense, balance and category breakdown' '- fixture: income 1000 ₽ / Продукты; expense 300 ₽ / Транспорт; outside-period expense 200 ₽' '- expected: unit and UI P0-03 checks pass, with reviewable screenshot attachment' "- observed: xcodebuild_test=$TEST_STATUS, screenshot_attachments=$SCREENSHOT_COUNT, attachment_export=$ATTACHMENT_EXPORT_STATUS" "- run_status: $G4_STATUS" ''
  printf '%s\n' '### Reviewable XCUITest artifacts' '' '- required_screenshot_attachments: p0-03-selected-period-statistics' "- observed_screenshot_attachment_files: $SCREENSHOT_COUNT" "- screenshot_attachment_status: $(if [ "$SCREENSHOT_COUNT" -ge 1 ]; then printf 'PASS'; else printf 'FAIL'; fi)" '- assertions: stored in Xcode result bundle and versioned test summary' '- Computer Use: not required for this automated proof' '' "## Итог: $OVERALL_STATUS" ''
  printf '%s\n' 'Временные логи находятся в системном TMPDIR и не являются доказательством; versioned report, result bundle, digest manifest и proof-record записываются только в новый каталог run_id.'
} > "$RUN_DIR/report.md.tmp"

if ! mv -n "$RUN_DIR/report.md.tmp" "$REPORT"; then
  printf '%s\n' "Refusing to overwrite report: $REPORT" >&2
  exit 1
fi

MANIFEST_SHA256="$(shasum -a 256 "$MANIFEST" | cut -d ' ' -f 1)"
REPORT_SHA256="$(shasum -a 256 "$REPORT" | cut -d ' ' -f 1)"
python3 - "$PROOF_RECORD" "$RUN_ID" "$MANIFEST" "$MANIFEST_SHA256" "$REPORT" "$REPORT_SHA256" "$TEST_RESULT_BUNDLE" "$XCRESULT_FILES_MANIFEST" "$XCRESULT_DIGEST" "$SCREENSHOT_COUNT" "$ATTACHMENT_EXPORT_STATUS" "$TEST_STATUS" "$TEST_DURATION_SECONDS" "$G1_STATUS" "$G4_STATUS" "$OVERALL_STATUS" <<'PY'
import json, sys
from pathlib import Path
proof_path = Path(sys.argv[1])
(run_id, manifest, manifest_sha256, report, report_sha256, result_bundle, result_manifest, result_digest, screenshot_count, attachment_export_status, test_status, duration, g1, g4, overall) = sys.argv[2:]
payload = {
    "proof_record_version": 1, "run_id": run_id, "outcome": "P0-03",
    "manifest": {"path": manifest, "sha256": manifest_sha256},
    "report": {"path": report, "sha256": report_sha256},
    "gate_results": {"G1": g1, "G4": g4}, "overall_result": overall,
    "ui_evidence": {"xcodebuild_test": {"status": int(test_status), "duration_seconds": int(duration), "result_bundle": result_bundle}, "xcresult_files_manifest": {"path": result_manifest, "digest_sha256": result_digest}, "screenshot_attachments": {"required": ["p0-03-selected-period-statistics"], "observed_file_count": int(screenshot_count), "attachment_export_status": int(attachment_export_status), "status": "PASS" if int(screenshot_count) >= 1 else "FAIL"}, "computer_use_required": False},
    "durable_artifacts": [manifest, report, result_bundle, result_manifest, str(proof_path)], "temporary_logs_are_evidence": False,
}
temporary = proof_path.with_suffix(".json.tmp")
temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
temporary.replace(proof_path)
PY

[ "$OVERALL_STATUS" = "PASS" ]
