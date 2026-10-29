"""Independent synthetic second-chance AV to validate CDB capture, never product code.

Deliberately crashes only an isolated throwaway Python child under Microsoft CDB.
Private debugger stdout exists temporarily and is never archived. The GitHub
artifact contains only allowlisted exception details and module!symbol strings.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from p6_native_cdb_trace import debugger, sanitize, persist, MARKER


NATIVE_C_SOURCE = r"""#include <windows.h>
int main(void) {
    volatile unsigned char * volatile invalid_pointer = (volatile unsigned char *)1;
    *invalid_pointer = 7;
    return 9;
}
"""


def compile_native_control(private: Path) -> Path | None:
    """Use only installed Microsoft Visual C++ compiler; never download tools."""
    root = Path(os.environ.get("ProgramFiles(x86)", r"C:\\Program Files (x86)"))
    vswhere = root / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
    if not vswhere.is_file():
        return None
    lookup = subprocess.run(
        [str(vswhere), "-latest", "-products", "*", "-property", "installationPath"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, encoding="utf-8", errors="replace", timeout=20, check=False,
    )
    install = Path(lookup.stdout.strip()) if lookup.returncode == 0 and lookup.stdout.strip() else None
    vcvars = (install / "VC" / "Auxiliary" / "Build" / "vcvars64.bat") if install else None
    if vcvars is None or not vcvars.is_file():
        return None
    source = private / "synthetic_fault.c"
    executable = private / "synthetic_fault.exe"
    source.write_text(NATIVE_C_SOURCE, encoding="ascii")
    command = 'call "' + str(vcvars) + '" >NUL && cl.exe /nologo /Od /TC /W3 /Fe:"' + str(executable) + '" "' + str(source) + '" >NUL'
    result = subprocess.run(["cmd.exe", "/d", "/s", "/c", command],
                            cwd=private, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            timeout=70, check=False)
    if result.returncode == 0 and executable.is_file():
        return executable
    # Clang-cl is preinstalled on the same trusted Windows runner; it uses the
    # already-initialized Microsoft Windows SDK/linker from vcvars64.bat.
    fallback = command.replace("cl.exe /nologo", "clang-cl.exe /nologo")
    result = subprocess.run(["cmd.exe", "/d", "/s", "/c", fallback],
                            cwd=private, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            timeout=70, check=False)
    return executable if result.returncode == 0 and executable.is_file() else None


def control(output: Path) -> int:
    output.mkdir(parents=True, exist_ok=False)
    exe = debugger()
    state = {
        "kind": "synthetic_second_chance_access_violation_cdb_control",
        "synthetic_only": True,
        "synthetic_method": "native_msvc_write_address_one",
        "production_source_executed": False,
        "debugger_available": bool(exe),
        "expected_code": "0xC0000005",
        "memory_dump_written": False,
        "raw_debugger_logs_uploaded": False,
        "test_control_passed": False,
        "started_utc":datetime.now(timezone.utc).isoformat(),
    }
    persist(output/"control.json", state)
    if not exe:
        state["status"]="BLOCKED_CDB_ABSENT"
        persist(output/"control.json",state)
        return 2
    # Native MSVC binary deliberately faults at address 1 in a separate process.
    command = f'sxd -c2 ".echo {MARKER}; .lastevent; .ecxr; kn 32; q" av; g'
    with tempfile.TemporaryDirectory(prefix="p6-cdb-control-private-") as private:
        executable = compile_native_control(Path(private))
        if executable is None:
            state["status"] = "BLOCKED_NO_TRUSTED_MSVC_COMPILER"
            persist(output/"control.json", state)
            return 3
        raw = Path(private)/"private.txt"
        cmd = [str(exe), "-G", "-c", command, str(executable)]
        with raw.open("wb") as stream:
            child = subprocess.Popen(cmd, stdout=stream, stderr=subprocess.STDOUT)
            try:
                exit_code=child.wait(timeout=65)
                timed_out=False
            except subprocess.TimeoutExpired:
                child.kill()
                exit_code=child.wait(timeout=10)
                timed_out=True
        parsed=sanitize(raw.read_bytes()[:5_000_000].decode("utf8", errors="replace"))
    state.update({
        "debugger_exit_code":exit_code,
        "timed_out":timed_out,
        "control_second_chance_marked":parsed["second_chance_marker"],
        "exception_code_verified":parsed["exception_codes"]==["0xC0000005"],
        "stack_symbols":parsed["native_stack_symbols"][:20],
        "native_stack_available":parsed["native_stack_available"],
        "root_cause_proven_for_product":False,
        "finished_utc":datetime.now(timezone.utc).isoformat(),
    })
    state["test_control_passed"]=bool(
        not timed_out and state["control_second_chance_marked"]
        and state["exception_code_verified"] and state["native_stack_available"]
    )
    state["status"]="CONTROL_PASS" if state["test_control_passed"] else "CONTROL_FAIL"
    persist(output/"control.json",state)
    print(json.dumps({
        "control_status":state["status"],
        "observed_native":state["control_second_chance_marked"],
        "observed_0xc0000005":state["exception_code_verified"],
        "stack_available":state["native_stack_available"],
        "symbols":state["stack_symbols"][:8],
    }),flush=True)
    return 0 if state["test_control_passed"] else 1


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if sys.platform!="win32" or os.environ.get("QT_QPA_PLATFORM")!="windows":
        parser.error("Windows native Qt CI is required")
    raise SystemExit(control(args.output))
