"""Read-only CDB second-chance crash capture for StructuralPro P6-5.

Never upload raw debugger output, process arguments, user paths, register
values, local variables, or memory dumps. Only native module!symbol names and
exception code survive sanitization. A real single-test JUnit is mandatory.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

TESTS = {
    "integrated": "tests/test_manual_formula_fivefloor_closure.py::test_real_qt_fourteen_operations_five_floors_and_all_reports",
    "dialog_commit": "scripts/diagnostics/p6_native_isolation_oracles.py::test_native_real_manual_dialog_review_commit_70_rows",
    "dialog_lifecycle": "scripts/diagnostics/p6_native_isolation_oracles.py::test_native_real_dialog_destroy_reopen_every_fourteen_commits",
}
MARKER = "P6_AV_SECOND_CHANCE"
MODULE_BEGIN = "P6_FAULT_PC_MODULE_BEGIN"
MODULE_END = "P6_FAULT_PC_MODULE_END"
NEAR_BEGIN = "P6_FAULT_PC_NEAREST_BEGIN"
NEAR_END = "P6_FAULT_PC_NEAREST_END"
STACK_BEGIN = "P6_FAULT_STACK_BEGIN"
SYM = re.compile(r"\b([A-Za-z_][A-Za-z0-9_.-]{0,70})!([A-Za-z_?$@][A-Za-z0-9_?$@.:+<>-]{0,115})")


def debugger() -> Path | None:
    options = [
        Path(os.environ.get("CDB_PATH", "")),
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Windows Kits/10/Debuggers/x64/cdb.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Windows Kits/10/Debuggers/x64/cdb.exe",
    ]
    return next((p for p in options if p.is_file() and p.name.lower() == "cdb.exe"), None)


def junit(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        cases = list(ET.parse(path).getroot().iter("testcase"))
    except (OSError, ET.ParseError):
        return {"valid": False, "reason": "INVALID_JUNIT"}
    result = {"total": len(cases)}
    for tag in ("failure", "error", "skipped"):
        result[tag] = sum(c.find(tag) is not None for c in cases)
    result["passed"] = sum(all(c.find(tag) is None for tag in ("failure", "error", "skipped")) for c in cases)
    result["valid"] = result["total"] == result["passed"] == 1
    return result


def sanitize(raw: str) -> dict:
    # CDB echoes the startup command containing MARKER even on clean exits.
    # Accept ONLY a standalone .echo output line, never a substring of command text.
    marker_lines = list(re.finditer(r"(?m)^\s*" + re.escape(MARKER) + r"\s*$", raw))
    crash = bool(marker_lines)
    section = raw[marker_lines[-1].end():] if crash else ""
    code_in_section = bool(re.search(r"(?i)\b(?:0x)?c0000005\b", section))
    lines = section.splitlines()

    def marked(start: str, end: str | None) -> list[str]:
        # Require a full standalone output line; CDB echoes its initial commands.
        indices = [i for i, line in enumerate(lines) if line.strip() == start]
        if not indices:
            return []
        index = indices[-1] + 1
        stop = next((i for i in range(index, len(lines))
                     if end and lines[i].strip() == end), len(lines))
        return lines[index:stop]

    # lm a @rip maps the exception-context PC to the loaded PE module.
    # Do not infer the faulting module from later stack frames.
    module_output = marked(MODULE_BEGIN, MODULE_END) if crash else []
    pc_module = None
    for line in module_output:
        m = re.match(
            r"^\s*[0-9A-Fa-f\x60]{8,24}\s+[0-9A-Fa-f\x60]{8,24}\s+([A-Za-z_][A-Za-z0-9_.-]{0,70})(?:\s|$)",
            line,
        )
        if m:
            pc_module = m.group(1).lower()
            break

    near_output = marked(NEAR_BEGIN, NEAR_END) if crash else []
    pc_symbol = None
    for line in near_output:
        m = SYM.search(line)
        if m and pc_module and m.group(1).lower() == pc_module:
            pc_symbol = m.group(1).lower() + "!" + m.group(2).split("+0x", 1)[0]
            break

    stack_output = marked(STACK_BEGIN, None) if crash else []
    # Only legacy parser self-check fixtures lack phase markers.
    if crash and not stack_output and STACK_BEGIN not in section:
        stack_output = lines
    frames = []
    for line in stack_output:
        if len(frames) == 32:
            break
        if not re.match(r"^\s*[0-9A-Fa-f]{1,2}\s+", line):
            continue
        m = SYM.search(line)
        if m:
            f = m.group(1).lower() + "!" + m.group(2).split("+0x", 1)[0]
            if f not in frames:
                frames.append(f)
    return {
        "second_chance_marker": crash,
        "exception_codes": ["0xC0000005"] if crash and code_in_section else [],
        "exception_code_observed": code_in_section,
        "native_pc_module": pc_module,
        "native_pc_module_proven_by_lm_address": bool(pc_module),
        "native_pc_nearest_symbol": pc_symbol,
        "native_stack_symbols": frames,
        "native_stack_available": bool(frames),
        "root_cause_proven": False,
        "raw_debugger_output_saved": False,
        "memory_dump_saved": False,
        "file_paths_saved": False,
    }


def persist(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".partial")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)


def run(output: Path, arm: str, repetitions: int, timeout: int, faulthandler_mode="enabled", dump_timeout=45) -> int:
    output.mkdir(parents=True, exist_ok=False)
    cdb = debugger()
    state = {
        "kind": "p6_native_windows_cdb_live_exception_no_dump",
        "arm": arm,
        "faulthandler_mode": faulthandler_mode,
        "dump_timeout": dump_timeout,
        "source_test": TESTS[arm],
        "debugger_available": cdb is not None,
        "debugger_kind": "Microsoft CDB",
        "original_test_unchanged": True,
        "product_code_unchanged": True,
        "raw_logs_uploaded": False,
        "memory_dumps_uploaded": False,
        "native_root_cause_proven": False,
        "marker_parser": "exception_pc_lm_address_v3",
        "status": "RUNNING" if cdb else "BLOCKED_NO_DEBUGGER",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "attempts": [],
    }
    persist(output / "summary.json", state)
    if not cdb:
        print("CDB_NOT_AVAILABLE: cannot claim a passing native diagnostic", flush=True)
        return 2
    for attempt in range(1, repetitions + 1):
        xml = output / f"attempt-{attempt}.xml"
        # CDB catches *second-chance* AV only, not handled first-chance exceptions.
        # kn prints call-stack symbols, not memory/registers/function arguments.
        crash_commands = (
            f".echo {MARKER}; .lastevent; .ecxr; "
            f".echo {MODULE_BEGIN}; lm a @rip; .echo {MODULE_END}; "
            f".echo {NEAR_BEGIN}; ln @rip; .echo {NEAR_END}; "
            f".echo {STACK_BEGIN}; kn 32; q"
        )
        startup = f'sxd -c2 "{crash_commands}" av; g'
        args = [
            str(cdb), "-G", "-c", startup,
            sys.executable, "-m", "pytest", "-q", "--disable-warnings",
            *(["-o", f"faulthandler_timeout={dump_timeout}"] if faulthandler_mode=="enabled" else ["-p", "no:faulthandler"]),
            "-p", "scripts.diagnostics.p6_faulthandler_probe", f"--junitxml={xml}", TESTS[arm],
        ]
        env = os.environ.copy()
        if faulthandler_mode=="enabled": env["PYTHONFAULTHANDLER"] = "1"
        else: env.pop("PYTHONFAULTHANDLER",None)
        env["P6_EXPECT_FAULTHANDLER"] = faulthandler_mode
        env["P6_EXPECT_DUMP_TIMEOUT"] = str(dump_timeout)
        env["P6_FH_PROBE"] = str(output / f"faulthandler-{attempt}.json")
        if arm == "dialog_lifecycle" and os.environ.get("P6_LIFECYCLE_CHECKPOINTS") == "1":
            env["P6_LIFECYCLE_CHECKPOINT_DIR"] = str(output / f"checkpoints-{attempt}")
        else:
            env.pop("P6_LIFECYCLE_CHECKPOINT_DIR", None)
        process_started_utc = datetime.now(timezone.utc).isoformat()
        start = time.monotonic()
        timed_out = False
        # Unredacted debugger output only exists in a transient directory,
        # never the GitHub artifact directory or the public step log.
        with tempfile.TemporaryDirectory(prefix="p6-cdb-ephemeral-") as private_dir:
            raw_path = Path(private_dir) / "unredacted-debugger-output.txt"
            with raw_path.open("wb") as fh:
                proc = subprocess.Popen(args, stdout=fh, stderr=subprocess.STDOUT, env=env)
                try:
                    exit_code = proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    proc.kill()
                    exit_code = proc.wait(timeout=15)
            native = sanitize(raw_path.read_bytes()[:12_000_000].decode("utf-8", errors="replace"))
        process_ended_utc = datetime.now(timezone.utc).isoformat()
        result = junit(xml)
        valid = bool(
            exit_code == 0 and not timed_out and not native["second_chance_marker"]
            and result is not None and result.get("valid")
        )
        state["attempts"].append({
            "attempt": attempt,
            "process_started_utc": process_started_utc,
            "process_ended_utc": process_ended_utc,
            "wall_seconds": round(time.monotonic() - start, 2),
            "debugger_exit_code": exit_code,
            "timed_out": timed_out,
            "junit": result,
            "valid_test_pass": valid,
            **native,
        })
        state["all_valid"] = all(x["valid_test_pass"] for x in state["attempts"])
        persist(output / "summary.json", state)
        print(json.dumps({
            "arm": arm, "attempt": attempt, "valid_junit": valid,
            "second_chance_av": native["second_chance_marker"],
            "native_stack": native["native_stack_symbols"][:12]
        }), flush=True)
    state["status"] = "PASS_LIMITED" if state["all_valid"] else "RED_OR_INCOMPLETE"
    state["ended_utc"] = datetime.now(timezone.utc).isoformat()
    persist(output / "summary.json", state)
    return 0 if state["all_valid"] else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--arm", choices=tuple(TESTS), default="integrated")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=420)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--faulthandler", choices=("enabled","disabled"), default="enabled")
    parser.add_argument("--dump-timeout", type=int, choices=(0,45), default=45)
    opts = parser.parse_args()
    if opts.self_check:
        fake = (f"{MARKER}\nExceptionCode: c0000005\n"
                "00 0011223344556677 00000000 Qt6Widgets!QWidget::event+0x4\n"
                "01 0011223344556677 00000000 python312!PyEval_EvalFrameDefault+0x3\n"
                "PRIVATE=C:\\Users\\Hidden\\secret\n")
        clean = sanitize(fake)
        assert clean["second_chance_marker"] and clean["exception_codes"] == ["0xC0000005"]
        assert len(clean["native_stack_symbols"]) == 2 and "Hidden" not in json.dumps(clean)
        assert not sanitize("first-chance access violation")["second_chance_marker"]
        synthetic = (
            f"{MARKER}\nExceptionCode: c0000005\n"
            f"{MODULE_BEGIN}\n00000000`01000000 00000000`01005000 synthetic_fault (deferred)\n"
            f"{MODULE_END}\n{NEAR_BEGIN}\n"
            "(00000000`01000100) synthetic_fault!main+0x4\n"
            f"{NEAR_END}\n{STACK_BEGIN}\n"
            "00 0011223344556677 00000000 kernel32!BaseThreadInitThunk+0x1\n"
        )
        native = sanitize(synthetic)
        assert native["native_pc_module"] == "synthetic_fault"
        assert native["native_pc_module_proven_by_lm_address"]
        assert native["native_pc_nearest_symbol"] == "synthetic_fault!main"
        assert not sanitize(f'0:000> .echo {MODULE_BEGIN}; lm a @rip; .echo {MODULE_END}')["native_pc_module"]
        assert not sanitize(f'0:000> sxd -c2 ".echo {MARKER}; .lastevent" av; g')["second_chance_marker"]
        assert junit(Path("file-does-not-exist.xml")) is None
        print("CDB sanitizer self-check PASS")
        return 0
    if sys.platform != "win32" or os.environ.get("QT_QPA_PLATFORM") != "windows":
        parser.error("Native Windows Qt is required")
    if opts.output is None or not 1 <= opts.repeats <= 3 or not 90 <= opts.timeout <= 500:
        parser.error("Unsupported diagnostic bounds")
    return run(opts.output, opts.arm, opts.repeats, opts.timeout, opts.faulthandler, opts.dump_timeout)


if __name__ == "__main__":
    sys.exit(main())
