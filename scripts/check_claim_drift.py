#!/usr/bin/env python3
"""Re-run the offline suites and fail if documented counts drift.

The integers in evidence/offline-claims.json must match:

- `python -m pytest` in engineering/memory-system (summary line "N passed")
- `node test/forgetting.test.mjs` ("TOTAL: N PASS / M FAIL")

Live surfaces must contain the phrases built from those integers
(`pytest passed: N`, `forgetting-js assertions: N`). Markdown and YAML
files are scanned for other suite-count claims. A file or line that
contains the marker COUNT-HISTORICAL is a point-in-time note and is
not required to match the live count.

This script does not run the research simulators and does not treat
their JSON as new findings.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLAIMS = ROOT / "evidence" / "offline-claims.json"
MARKER = "COUNT-HISTORICAL"
SCAN_SUFFIXES = {".md", ".yml", ".yaml"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}

PASSED_RE = re.compile(r"(\d+)\s+passed\b")
ASSERTIONS_RE = re.compile(r"(\d+)\s+assertions\b", re.IGNORECASE)
PASS_RE = re.compile(r"(\d+)\s+PASS\b")
TESTS_PASSING_RE = re.compile(r"(\d+)\s+tests passing\b", re.IGNORECASE)
PYTEST_SUMMARY_RE = re.compile(r"(\d+)\s+passed\b")
JS_TOTAL_RE = re.compile(r"TOTAL:\s*(\d+)\s+PASS\s*/\s*(\d+)\s+FAIL")


def fail(errors: list[str]) -> None:
    print("claim drift: FAIL", file=sys.stderr)
    for err in errors:
        print(f"- {err}", file=sys.stderr)
    sys.exit(1)


def load_claims() -> dict:
    data = json.loads(CLAIMS.read_text(encoding="utf-8"))
    for key in (
        "pytest_passed",
        "forgetting_js_assertions_passed",
        "forgetting_js_assertions_failed",
        "live_surfaces",
    ):
        if key not in data:
            raise SystemExit(f"offline-claims.json missing {key}")
    return data


def run_pytest(claims: dict) -> str:
    cwd = ROOT / claims["pytest_cwd"]
    cmd = [sys.executable, "-m", "pytest", *claims["pytest_args"]]
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if proc.returncode != 0:
        tail = "\n".join(text.strip().splitlines()[-20:])
        raise SystemExit(f"pytest exited {proc.returncode}\n{tail}")
    return text


def parse_pytest_passed(text: str) -> int:
    matches = PYTEST_SUMMARY_RE.findall(text)
    if not matches:
        raise SystemExit(f"could not parse pytest summary:\n{text[-500:]}")
    # The summary is the last "N passed" line. A failed run is already rejected.
    if re.search(r"\d+\s+failed\b", text):
        raise SystemExit(f"pytest reported failures:\n{text[-500:]}")
    return int(matches[-1])


def run_js(claims: dict) -> str:
    cwd = ROOT / claims["forgetting_js_cwd"]
    script = claims["forgetting_js_script"]
    proc = subprocess.run(
        ["node", script],
        cwd=cwd,
        text=True,
        capture_output=True,
    )
    text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if proc.returncode != 0:
        tail = "\n".join(text.strip().splitlines()[-20:])
        raise SystemExit(f"node forgetting tests exited {proc.returncode}\n{tail}")
    return text


def parse_js(text: str) -> tuple[int, int]:
    matches = JS_TOTAL_RE.findall(text)
    if not matches:
        raise SystemExit(f"could not parse JS total line:\n{text[-500:]}")
    passed, failed = matches[-1]
    return int(passed), int(failed)


def phrase(template: str, pytest_n: int, js_n: int) -> str:
    return template.replace("{pytest}", str(pytest_n)).replace("{js}", str(js_n))


def check_live_surfaces(claims: dict, pytest_n: int, js_n: int, errors: list[str]) -> None:
    for surface in claims["live_surfaces"]:
        path = ROOT / surface["path"]
        if not path.is_file():
            errors.append(f"missing live surface {surface['path']}")
            continue
        text = path.read_text(encoding="utf-8")
        for template in surface["must_contain"]:
            needed = phrase(template, pytest_n, js_n)
            if needed not in text:
                errors.append(f"{surface['path']} does not contain {needed!r}")


def line_is_js_count(line: str, match_end: int) -> bool:
    # Only the words immediately after the count. A later "JS" on the same
    # line must not reclassify a pytest summary ("112 passed in 3.74s; JS ...").
    window = line[match_end : match_end + 10].lower()
    return "js" in window or window.startswith(" forgetting")


def scan_tree(pytest_n: int, js_n: int, errors: list[str]) -> None:
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in SCAN_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if MARKER in text[:1500]:
            continue
        rel = path.relative_to(ROOT).as_posix()
        for lineno, line in enumerate(text.splitlines(), start=1):
            if MARKER in line:
                continue
            for regex, kind in (
                (PASSED_RE, "passed"),
                (ASSERTIONS_RE, "assertions"),
                (PASS_RE, "PASS"),
                (TESTS_PASSING_RE, "tests passing"),
            ):
                for match in regex.finditer(line):
                    number = int(match.group(1))
                    if kind == "assertions":
                        prefix = line[max(0, match.start() - 6):match.start()].lower()
                        if prefix.endswith("node ") or prefix.endswith("node"):
                            continue
                    if kind == "passed":
                        expect = js_n if line_is_js_count(line, match.end()) else pytest_n
                        label = "forgetting-js" if expect == js_n else "pytest"
                    elif kind == "tests passing":
                        expect = pytest_n
                        label = "pytest"
                    else:
                        expect = js_n
                        label = "forgetting-js"
                    if number != expect:
                        errors.append(
                            f"{rel}:{lineno} claims {number} {kind}; live {label} count is {expect}. "
                            f"Update the line or mark it {MARKER}."
                        )


def main() -> None:
    claims = load_claims()
    pytest_text = run_pytest(claims)
    pytest_n = parse_pytest_passed(pytest_text)
    js_text = run_js(claims)
    js_pass, js_fail = parse_js(js_text)

    errors: list[str] = []
    if pytest_n != claims["pytest_passed"]:
        errors.append(
            f"pytest passed {pytest_n}, evidence/offline-claims.json says {claims['pytest_passed']}"
        )
    if js_pass != claims["forgetting_js_assertions_passed"]:
        errors.append(
            "forgetting-js PASS "
            f"{js_pass}, evidence/offline-claims.json says {claims['forgetting_js_assertions_passed']}"
        )
    if js_fail != claims["forgetting_js_assertions_failed"]:
        errors.append(
            f"forgetting-js FAIL {js_fail}, expected {claims['forgetting_js_assertions_failed']}"
        )
    check_live_surfaces(claims, claims["pytest_passed"], claims["forgetting_js_assertions_passed"], errors)
    scan_tree(claims["pytest_passed"], claims["forgetting_js_assertions_passed"], errors)
    if errors:
        fail(errors)
    print(
        "claim drift: OK "
        f"(pytest passed: {pytest_n}; forgetting-js assertions: {js_pass})"
    )


if __name__ == "__main__":
    main()
