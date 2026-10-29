"""Calibrate CDB using an isolated, deterministic Windows native AV.

A tiny trusted compiler/linker builds a test-only PE with NO CRT, Qt, SQLite,
project sources or imports. The PE deliberately writes address 0x1 and is run
only in a fresh CDB child. Compiler diagnostics are reduced to categorized
codes; raw debugger logs and paths are deleted inside a temporary directory.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from p6_native_cdb_trace import debugger, sanitize, persist, MARKER

NATIVE_C_SOURCE = """
int main(void) {
    volatile unsigned char * volatile bad = (volatile unsigned char *)1;
    *bad = 7;
    for (;;) {}
}
"""
# Permit only known compiler/linker numeric error IDs in archived diagnostics.
ERR_CODE = re.compile(r"\b(?:C\d{4}|D\d{4}|LNK\d{4}|LINK\d{4}|[A-Z]+\d{3,5})\b")
EXE_NAME = "synthetic_fault.exe"


def toolchain_probe(directory: Path) -> tuple[Path | None, dict]:
    """Build without Windows headers, SDK libraries, VS vcvars or C runtime."""
    source = directory / "synthetic_fault.c"
    obj = directory / "synthetic_fault.obj"
    executable = directory / EXE_NAME
    source.write_text(NATIVE_C_SOURCE, encoding="ascii")
    clang = shutil.which("clang-cl.exe")
    # First choice is LLVM lld-link. Trusted Microsoft link.exe is acceptable.
    linker = shutil.which("lld-link.exe") or shutil.which("link.exe")
    meta = {
        "kind": "native_no_crt_headerless_compile",
        "compiler": "clang-cl" if clang else "unavailable",
        "linker": "lld-link" if linker and Path(linker).stem.lower() == "lld-link"
                  else "link" if linker else "unavailable",
        "compiler_present": bool(clang),
        "linker_present": bool(linker),
        "compile_return_code": None,
        "link_return_code": None,
        "compiler_error_codes": [],
        "linker_error_codes": [],
        "compile_object_exists": False,
        "linked_executable_exists": False,
        "includes_windows_headers": False,
        "uses_crt": False,
        "raw_build_output_saved": False,
    }
    if not clang or not linker:
        meta["blocker"] = "MISSING_COMPILER_OR_LINKER"
        return None, meta
    compile_argv = [
        clang, "/nologo", "/Od", "/GS-", "/c", "/TC",
        "/Fo" + str(obj), str(source),
    ]
    link_argv = [
        linker, "/nologo", "/machine:x64", "/subsystem:console",
        "/entry:main", "/nodefaultlib",
        "/out:" + str(executable), str(obj),
    ]

    def execute(argv: list[str]) -> tuple[int, list[str]]:
        try:
            p = subprocess.run(
                argv, cwd=directory, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                check=False, timeout=50,
            )
            return p.returncode, sorted(set(ERR_CODE.findall(p.stdout)))[:12]
        except subprocess.TimeoutExpired:
            return 124, []
        except OSError:
            return 127, []

    rc, codes = execute(compile_argv)
    meta["compile_return_code"] = rc
    meta["compiler_error_codes"] = codes
    meta["compile_object_exists"] = obj.is_file()
    if rc != 0 or not obj.is_file():
        meta["blocker"] = "COMPILATION_FAILED"
        return None, meta
    rc, codes = execute(link_argv)
    meta["link_return_code"] = rc
    meta["linker_error_codes"] = codes
    meta["linked_executable_exists"] = executable.is_file()
    if rc != 0 or not executable.is_file():
        meta["blocker"] = "LINK_FAILED"
        return None, meta
    return executable, meta


def control(output: Path) -> int:
    output.mkdir(parents=True, exist_ok=False)
    cdb = debugger()
    state = {
        "kind": "p6_synthetic_second_chance_av_no_dump_calibration_v3",
        "synthetic_only": True,
        "production_source_executed": False,
        "original_oracle_unchanged": True,
        "debugger_present": bool(cdb),
        "expected_code": "0xC0000005",
        "memory_dump_written": False,
        "raw_debugger_logs_uploaded": False,
        "native_root_cause_proven_for_product": False,
        "test_control_passed": False,
        "started_utc": datetime.now(timezone.utc).isoformat(),
    }
    persist(output / "control.json", state)
    if not cdb:
        state["status"] = "BLOCKED_CDB_NOT_INSTALLED"
        persist(output / "control.json", state)
        return 2
    with tempfile.TemporaryDirectory(prefix="p6-native-av-control-") as temp:
        root = Path(temp)
        executable, build = toolchain_probe(root)
        state["build"] = build
        persist(output / "control.json", state)
        if not executable:
            state["status"] = build.get("blocker", "BUILD_FAILED")
            persist(output / "control.json", state)
            print(json.dumps({"status": state["status"], "build": build}), flush=True)
            return 3
        # sxd: ignore first chance, break on second chance. No .dump commands.
        commands = f'sxd -c2 ".echo {MARKER}; .lastevent; .ecxr; kn 32; q" av; g'
        raw = root / "unredacted-debugger-output.txt"
        with raw.open("wb") as stream:
            process = subprocess.Popen(
                [str(cdb), "-G", "-c", commands, str(executable)],
                stdout=stream, stderr=subprocess.STDOUT,
            )
            try:
                exit_code = process.wait(timeout=90)
                timed_out = False
            except subprocess.TimeoutExpired:
                process.kill()
                exit_code = process.wait(timeout=12)
                timed_out = True
        observed = sanitize(raw.read_bytes()[:6_000_000].decode("utf-8", errors="replace"))
    state.update({
        "debugger_exit_code": exit_code,
        "timed_out": timed_out,
        "control_second_chance_marked": observed["second_chance_marker"],
        "exception_code_verified": observed["exception_codes"] == ["0xC0000005"],
        "native_stack_symbols": observed["native_stack_symbols"][:20],
        "native_stack_available": observed["native_stack_available"],
        "finished_utc": datetime.now(timezone.utc).isoformat(),
    })
    state["test_control_passed"] = bool(
        not timed_out and state["control_second_chance_marked"]
        and state["exception_code_verified"] and state["native_stack_available"]
    )
    state["status"] = "CONTROL_PASS" if state["test_control_passed"] else "CONTROL_RED"
    persist(output / "control.json", state)
    print(json.dumps({
        "status": state["status"],
        "second_chance": state["control_second_chance_marked"],
        "code_verified": state["exception_code_verified"],
        "stack_available": state["native_stack_available"],
        "symbols": state["native_stack_symbols"][:8],
    }), flush=True)
    return 0 if state["test_control_passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    opts = parser.parse_args()
    if sys.platform != "win32" or os.environ.get("QT_QPA_PLATFORM") != "windows":
        parser.error("The isolated control requires Windows native CI")
    raise SystemExit(control(opts.output))
