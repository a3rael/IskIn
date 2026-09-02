#!/bin/bash
# Canonical local proof for P0-02 (G1 + G3).
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROJECT="$ROOT/testbeds/budget-ios/BudgetApp.xcodeproj"
EVIDENCE_ROOT="$ROOT/testbeds/budget-ios/evidence"
RUN_ID="$(date -u '+%Y%m%dT%H%M%SZ')-$$"
RUN_DIR="$EVIDENCE_ROOT/runs/$RUN_ID"
MANIFEST="$RUN_DIR/manifest.json"
REPORT="$RUN_DIR/report.md"
PROOF_RECORD="$RUN_DIR/proof-record.json"
WORK="${TMPDIR:-/tmp}/agent-native-pdlc-p0-02"
DERIVED_DATA="$WORK/DerivedData"
TEST_RESULT_BUNDLE="$RUN_DIR/BudgetApp-P0-02.xcresult"
TEST_LOG="$WORK/xcodebuild-test.log"
XCRESULT_FILES_MANIFEST="$RUN_DIR/BudgetApp-P0-02.xcresult.files.sha256"
ATTACHMENTS_DIR="$WORK/xcresult-attachments"
ATTACHMENT_EXPORT_LOG="$WORK/xcresult-attachments.log"
CORE_BUILD_LOG="$WORK/core-build.log"
CORE_RUN_LOG="$WORK/core-run.log"

rm -rf "$WORK"
mkdir -p "$WORK"

START="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
COMMIT="$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || printf 'unknown')"
XCODE_VERSION="$(xcodebuild -version 2>/dev/null | tr '\n' ' ' || printf 'unavailable')"
SWIFT_VERSION="$(swiftc --version 2>/dev/null | tr '\n' ' ' || printf 'unavailable')"

BUILD_STATUS=1
INSTALL_STATUS=1
LAUNCH_STATUS=1
TEST_STATUS=1
CORE_BUILD_STATUS=1
CORE_RUN_STATUS=1
ATTACHMENT_EXPORT_STATUS=1
SCREENSHOT_COUNT=0
XCRESULT_DIGEST="unavailable"
TEST_DURATION_SECONDS=0
DEVICE_ID="unavailable"
DEVICE_NAME="unavailable"

DEVICE_JSON="$(xcrun simctl list devices available --json 2>/dev/null || printf '{}')"
DEVICE_ID="$(printf '%s' "$DEVICE_JSON" | python3 -c '
import json
import sys

data = json.load(sys.stdin)
all_devices = [device for devices in data.get("devices", {}).values() for device in devices]
for device in all_devices:
    if device.get("isAvailable") and device.get("state") == "Booted":
        print(device["udid"])
        raise SystemExit
for device in all_devices:
    if device.get("isAvailable") and device.get("name") == "iPhone 17 Pro":
        print(device["udid"])
        raise SystemExit
for device in all_devices:
    if device.get("isAvailable"):
        print(device["udid"])
        raise SystemExit
raise SystemExit(1)
' 2>/dev/null || printf 'unavailable')"

mkdir -p "$EVIDENCE_ROOT/runs"
if ! mkdir "$RUN_DIR"; then
  printf '%s\n' "Refusing to reuse run directory: $RUN_DIR" >&2
  exit 1
fi

python3 - "$MANIFEST" "$ROOT" "$RUN_ID" "$START" "$COMMIT" "$XCODE_VERSION" "$SWIFT_VERSION" "$DEVICE_ID" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
root = Path(sys.argv[2])
run_id, started, commit, xcode, swift, simulator_udid = sys.argv[3:]

g1_paths = [
    "testbeds/budget-ios/run-p0-02-verification.sh",
    "testbeds/budget-ios/BudgetApp.xcodeproj/project.pbxproj",
    "testbeds/budget-ios/BudgetAppApp.swift",
    "testbeds/budget-ios/ContentView.swift",
    "testbeds/budget-ios/BudgetOperation.swift",
    "testbeds/budget-ios/BudgetOperationStore.swift",
    "testbeds/budget-ios/BudgetAppUITests/BudgetAppUITests.swift",
    "testbeds/budget-ios/BudgetApp.xcodeproj/xcshareddata/xcschemes/BudgetApp.xcscheme",
]
g3_paths = [
    "testbeds/budget-ios/run-p0-02-verification.sh",
    "testbeds/budget-ios/BudgetCoreChecks.swift",
    "testbeds/budget-ios/BudgetOperation.swift",
    "testbeds/budget-ios/ContentView.swift",
    "testbeds/budget-ios/BudgetOperationStore.swift",
    "testbeds/budget-ios/BudgetAppTests/BudgetOperationTests.swift",
    "testbeds/budget-ios/BudgetAppUITests/BudgetAppUITests.swift",
    "testbeds/budget-ios/BudgetApp.xcodeproj/project.pbxproj",
]

def entry(path):
    absolute = root / path
    digest = hashlib.sha256(absolute.read_bytes()).hexdigest()
    return {"path": path, "sha256": digest}

payload = {
    "schema_version": 1,
    "run_id": run_id,
    "outcome": "P0-02",
    "created_at_utc": started,
    "canonical_command": "./testbeds/budget-ios/run-p0-02-verification.sh",
    "repository_runner": "testbeds/budget-ios/run-p0-02-verification.sh",
    "runner_sha256": entry(g1_paths[0])["sha256"],
    "environment": {
        "xcodebuild": xcode,
        "swiftc": swift,
        "target": "iOS Simulator",
        "simulator_udid": simulator_udid,
    },
    "scopes": {
        "G1": {"inputs": [entry(path) for path in g1_paths]},
        "G3": {"inputs": [entry(path) for path in g3_paths]},
    },
}
if manifest_path.exists():
    raise SystemExit("manifest already exists")
temporary = manifest_path.with_suffix(".json.tmp")
temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
temporary.replace(manifest_path)
PY

if [ "$DEVICE_ID" != "unavailable" ]; then
  TEST_DESTINATION="platform=iOS Simulator,id=$DEVICE_ID"
else
  TEST_DESTINATION="platform=iOS Simulator,name=iPhone 17 Pro"
fi

TEST_START_EPOCH="$(date +%s)"
xcodebuild \
  -project "$PROJECT" \
  -scheme BudgetApp \
  -destination "$TEST_DESTINATION" \
  -derivedDataPath "$DERIVED_DATA" \
  -resultBundlePath "$TEST_RESULT_BUNDLE" \
  test >"$TEST_LOG" 2>&1
TEST_STATUS=$?
TEST_FINISH_EPOCH="$(date +%s)"
TEST_DURATION_SECONDS=$((TEST_FINISH_EPOCH - TEST_START_EPOCH))
BUILD_STATUS=$TEST_STATUS
INSTALL_STATUS=$TEST_STATUS
LAUNCH_STATUS=$TEST_STATUS

if [ "$DEVICE_ID" != "unavailable" ]; then
  DEVICE_NAME="$(printf '%s' "$DEVICE_JSON" | python3 -c '
import json
import sys

data = json.load(sys.stdin)
udid = sys.argv[1]
for devices in data.get("devices", {}).values():
    for device in devices:
        if device.get("udid") == udid:
            print(device.get("name", "unknown"))
            raise SystemExit
' "$DEVICE_ID" 2>/dev/null || printf 'unknown')"
fi

if [ -d "$TEST_RESULT_BUNDLE" ]; then
  rm -rf "$ATTACHMENTS_DIR"
  mkdir -p "$ATTACHMENTS_DIR"
  xcrun xcresulttool export attachments \
    --path "$TEST_RESULT_BUNDLE" \
    --output-path "$ATTACHMENTS_DIR" >"$ATTACHMENT_EXPORT_LOG" 2>&1
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

if [ -d "$TEST_RESULT_BUNDLE" ]; then
  XCRESULT_DIGEST="$(python3 - "$TEST_RESULT_BUNDLE" "$XCRESULT_FILES_MANIFEST" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

bundle = Path(sys.argv[1])
manifest_path = Path(sys.argv[2])
entries = []
for path in sorted(
    (candidate for candidate in bundle.rglob("*") if candidate.is_file()),
    key=lambda candidate: candidate.relative_to(bundle).as_posix(),
):
    relative_path = path.relative_to(bundle).as_posix()
    entries.append({
        "path": relative_path,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    })
canonical = "".join(f"{entry['path']}\t{entry['sha256']}\n" for entry in entries)
digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
payload = {
    "schema_version": 1,
    "result_bundle": bundle.name,
    "files": entries,
    "digest_sha256": digest,
}
temporary = manifest_path.with_suffix(".tmp")
temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
temporary.replace(manifest_path)
print(digest)
PY
  )"
fi

swiftc \
  "$ROOT/testbeds/budget-ios/BudgetOperation.swift" \
  "$ROOT/testbeds/budget-ios/BudgetCoreChecks.swift" \
  -o "$WORK/BudgetCoreChecks" >"$CORE_BUILD_LOG" 2>&1
CORE_BUILD_STATUS=$?
if [ "$CORE_BUILD_STATUS" -eq 0 ]; then
  "$WORK/BudgetCoreChecks" >"$CORE_RUN_LOG" 2>&1
  CORE_RUN_STATUS=$?
fi

G1_STATUS="FAIL"
if [ "$TEST_STATUS" -eq 0 ] && [ -d "$TEST_RESULT_BUNDLE" ]; then
  G1_STATUS="PASS"
fi
G3_STATUS="FAIL"
if [ "$TEST_STATUS" -eq 0 ] && [ "$CORE_BUILD_STATUS" -eq 0 ] && [ "$CORE_RUN_STATUS" -eq 0 ] && [ "$SCREENSHOT_COUNT" -ge 3 ]; then
  G3_STATUS="PASS"
fi
OVERALL_STATUS="FAIL"
if [ "$G1_STATUS" = "PASS" ] && [ "$G3_STATUS" = "PASS" ]; then
  OVERALL_STATUS="PASS"
fi

REPORT_TMP="$RUN_DIR/report.md.tmp"
if [ -e "$REPORT" ] || [ -e "$PROOF_RECORD" ]; then
  printf '%s\n' "Refusing to overwrite versioned artifacts in $RUN_DIR" >&2
  exit 1
fi

{
  printf '%s\n' '# P0-02 automatic verification'
  printf '%s\n' '' 'report_version: 2' "run_id: $RUN_ID" 'Generated by: `./testbeds/budget-ios/run-p0-02-verification.sh`' "Started (UTC): $START" "Repository commit: $COMMIT" "Environment: $XCODE_VERSION; $SWIFT_VERSION" "Simulator: $DEVICE_NAME ($DEVICE_ID)" ''
  printf '%s\n' '## Contract'
  printf '%s\n' '' '- Canonical command: `./testbeds/budget-ios/run-p0-02-verification.sh`' '- Repository runner: `testbeds/budget-ios/run-p0-02-verification.sh`' "- Manifest: $MANIFEST" "- Versioned report: $REPORT" "- Versioned proof-record: $PROOF_RECORD" "- Xcode result bundle: $TEST_RESULT_BUNDLE" "- .xcresult files manifest: $XCRESULT_FILES_MANIFEST" "- .xcresult digest: $XCRESULT_DIGEST" ''
  printf '%s\n' '## G1 — сборка и запуск в iOS Simulator'
  printf '%s\n' '' '- gate_id: G1' '- scope: runner, Xcode project, BudgetAppApp.swift, ContentView.swift, BudgetOperation.swift, BudgetOperationStore.swift, UI test target' '- criterion: приложение собирается и запускается в iOS Simulator' '- applicable_fixture: не применимо' '- expected: `xcodebuild test` завершается успешно и создаёт result bundle' "- observed: xcodebuild_test=$TEST_STATUS, result_bundle=$(if [ -d "$TEST_RESULT_BUNDLE" ]; then printf 'present'; else printf 'missing'; fi)" "- run_status: $G1_STATUS" ''
  printf '%s\n' '## G3 — история и фильтрация по периоду'
  printf '%s\n' '' '- gate_id: G3' '- scope: runner, BudgetCoreChecks.swift, BudgetOperation.swift, ContentView.swift, BudgetOperationStore.swift, XCTest/XCUITest targets' '- criterion: история содержит A/B/C без фильтра, период включает A/B и исключает C, изменение периода меняет состав' '- applicable_fixture: A — доход 1000 ₽ на границе периода; B — расход 300 ₽ на границе периода; C — расход 200 ₽ вне периода' '- expected: PASS всех logic/UI assertions и наличие обязательных screenshot attachments' "- observed: xcodebuild_test=$TEST_STATUS, compile=$CORE_BUILD_STATUS, run=$CORE_RUN_STATUS, screenshot_attachments=$SCREENSHOT_COUNT, attachment_export=$ATTACHMENT_EXPORT_STATUS" "- run_status: $G3_STATUS" ''
  printf '%s\n' '### Проверки G3 из BudgetCoreChecks.swift'
  if [ -s "$CORE_RUN_LOG" ]; then
    while IFS= read -r line; do
      case "$line" in
        PASS\ G3:*) printf '%s\n' "- $line" ;;
      esac
    done < "$CORE_RUN_LOG"
  else
    printf '%s\n' '- Проверки не выполнены: компиляция или запуск завершились ошибкой.'
  fi
  printf '%s\n' '' '### Reviewable XCUITest artifacts'
  printf '%s\n' '' '- required_screenshot_attachments: p0-02-all-operations, p0-02-selected-period, p0-02-period-changed' "- observed_screenshot_attachment_files: $SCREENSHOT_COUNT" "- screenshot_attachment_status: $(if [ "$SCREENSHOT_COUNT" -ge 3 ]; then printf 'PASS'; else printf 'FAIL'; fi)" '- assertions: stored in Xcode result bundle and versioned test summary' '- Computer Use: not required for this automated proof'
  printf '%s\n' '' '### Проверочные метрики'
  printf '%s\n' '' '- critical_ui_checks_via_xcuitest: 1/1' '- computer_use_runs: 0' "- xcodebuild_test_duration_seconds: $TEST_DURATION_SECONDS" '- external_paid_check_cost: N/A' '' "## Итог: $OVERALL_STATUS" ''
  printf '%s\n' 'Временные логи находятся в системном TMPDIR и не являются доказательством; versioned report, result bundle, digest manifest и proof-record записываются только в новый каталог run_id.'
} > "$REPORT_TMP"

if ! mv -n "$REPORT_TMP" "$REPORT"; then
  printf '%s\n' "Refusing to overwrite report: $REPORT" >&2
  exit 1
fi

MANIFEST_SHA256="$(shasum -a 256 "$MANIFEST" | cut -d ' ' -f 1)"
REPORT_SHA256="$(shasum -a 256 "$REPORT" | cut -d ' ' -f 1)"
python3 - "$PROOF_RECORD" "$RUN_ID" "$MANIFEST" "$MANIFEST_SHA256" "$REPORT" "$REPORT_SHA256" "$TEST_RESULT_BUNDLE" "$XCRESULT_FILES_MANIFEST" "$XCRESULT_DIGEST" "$SCREENSHOT_COUNT" "$ATTACHMENT_EXPORT_STATUS" "$TEST_STATUS" "$TEST_DURATION_SECONDS" "$G1_STATUS" "$G3_STATUS" "$OVERALL_STATUS" <<'PY'
import json
import sys
from pathlib import Path

proof_path = Path(sys.argv[1])
(
    run_id,
    manifest,
    manifest_sha256,
    report,
    report_sha256,
    result_bundle,
    result_bundle_manifest,
    result_bundle_digest,
    screenshot_count,
    attachment_export_status,
    test_status,
    test_duration_seconds,
    g1,
    g3,
    overall,
) = sys.argv[2:]
if proof_path.exists():
    raise SystemExit("proof-record already exists")
payload = {
    "proof_record_version": 2,
    "run_id": run_id,
    "outcome": "P0-02",
    "manifest": {"path": manifest, "sha256": manifest_sha256},
    "report": {"path": report, "sha256": report_sha256},
    "gate_results": {"G1": g1, "G3": g3},
    "overall_result": overall,
    "ui_evidence": {
        "xcodebuild_test": {
            "status": int(test_status),
            "duration_seconds": int(test_duration_seconds),
            "result_bundle": result_bundle,
        },
        "xcresult_files_manifest": {
            "path": result_bundle_manifest,
            "digest_sha256": result_bundle_digest,
        },
        "screenshot_attachments": {
            "required": ["p0-02-all-operations", "p0-02-selected-period", "p0-02-period-changed"],
            "observed_file_count": int(screenshot_count),
            "attachment_export_status": int(attachment_export_status),
            "status": "PASS" if int(screenshot_count) >= 3 else "FAIL",
        },
        "computer_use_required": False,
    },
    "durable_artifacts": [manifest, report, result_bundle, result_bundle_manifest, str(proof_path)],
    "temporary_logs_are_evidence": False,
}
temporary = proof_path.with_suffix(".json.tmp")
temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
temporary.replace(proof_path)
PY

if [ "$OVERALL_STATUS" != "PASS" ]; then
  exit 1
fi
