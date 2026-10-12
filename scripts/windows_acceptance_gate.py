"""Source-only StructuralPro GUI/PDF Windows acceptance. No builds/Actions/releases.

Run from repo root: python scripts/windows_acceptance_gate.py --out-dir qa/windows
Returns: 0=passing technical smoke (visual approval still required),
         2=missing dependency / unsupported system, 1=failed smoke or unsafe source.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback

REQUIRED = ("PySide6", "arabic_reshaper", "bidi", "fitz", "reportlab", "docx", "openpyxl")


def active_workflows(repo: Path) -> list[str]:
    root = repo / ".github" / "workflows"
    if root.is_symlink():
        raise ValueError("workflow directory is a symlink: fail closed")
    if not root.exists():
        return []
    if not root.is_dir():
        raise ValueError("workflow path exists but is not directory")
    result = []
    for item in root.iterdir():
        if item.is_symlink():
            raise ValueError("workflow directory contains a symlink: fail closed")
        if item.suffix.lower() in (".yml", ".yaml") or item.is_dir():
            result.append(str(item.relative_to(repo)))
    return sorted(result)


def missing_dependencies() -> list[str]:
    return [name for name in REQUIRED if importlib.util.find_spec(name) is None]


def _atomic_json(path: Path, data: dict) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def smoke(repo: Path, output: Path) -> dict:
    """Run in child process because Qt platform plugins may terminate the interpreter."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QDialog
    from core.platform.application import StructuralProApp
    from app.manual_takeoff import ManualTakeoffDialog
    from core.reports.exporters import export_pdf
    import fitz

    app = QApplication.instance() or QApplication([])
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    if app.layoutDirection() != Qt.LayoutDirection.RightToLeft:
        raise AssertionError("Qt RTL application direction not set")
    with tempfile.TemporaryDirectory(prefix="structuralpro_windows_qa_") as temp:
        service = StructuralProApp(Path(temp))
        service.create_project("پروژه آزمایشی پذیرش", "QA-WIN")
        dlg = ManualTakeoffDialog(service, "QA-WIN")
        if not isinstance(dlg, QDialog):
            raise AssertionError("manual takeoff dialog was not constructed")
        if "متره" not in dlg.windowTitle():
            raise AssertionError("unexpected manual takeoff title")
        dlg.show()
        app.processEvents()
        if dlg.width() <= 100 or dlg.height() <= 100:
            raise AssertionError("dialog too small to inspect")
        screenshot = output / "qt_manual_takeoff.png"
        if not dlg.grab().save(str(screenshot)) or screenshot.stat().st_size < 300:
            raise AssertionError("Qt screenshot missing or empty")
        dlg.close()
        service.store.close()
        rows = [{"code":"0101", "description":"بتن پی", "quantity":2.5, "unit":"m3"}]
        cols = [("code","کد"),("description","شرح"),("quantity","مقدار"),("unit","واحد")]
        pdf = export_pdf(rows, output / "persian_report.pdf", title="گزارش متره آزمایشی", columns=cols)
        document = fitz.open(pdf)
        if document.page_count < 1:
            raise AssertionError("PDF empty")
        if not document[0].get_text().strip():
            raise AssertionError("PDF has no selectable text")
        render = output / "persian_report_page1.png"
        document[0].get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).save(str(render))
        document.close()
        if render.stat().st_size < 500:
            raise AssertionError("PDF rendering empty")
        return {"qt_rtl": True, "manual_takeoff_dialog": True,
                "screenshot": screenshot.name, "pdf": pdf.name,
                "pdf_render": render.name, "human_visual_approval": "PENDING"}


def perform(repo: Path, output: Path, *, force_platform: str | None = None,
            preflight_only: bool = False) -> tuple[dict, int]:
    output.mkdir(parents=True, exist_ok=True)
    report = {"schema": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
              "repo": str(repo), "platform": force_platform or sys.platform,
              "actions_executed": False, "build_or_release_produced": False,
              "human_visual_approval": "PENDING"}
    try:
        enabled = active_workflows(repo)
        report["active_workflows"] = enabled
        if enabled:
            report.update(status="BLOCKED_UNSAFE_WORKFLOWS", reason="active workflows present")
            return report, 1
        # Assert that we didn't remove the source of the historical audit.
        archived = repo / "recovery" / "disabled_workflows"
        if archived.is_symlink() or not archived.is_dir():
            raise ValueError("Quarantined workflows directory unavailable or linked")
        children = list(archived.iterdir())
        if any(item.is_symlink() or not item.is_file() or
               item.suffix.lower() not in {".yml", ".yaml"} for item in children):
            raise ValueError("Unexpected file type or symbolic link in quarantine")
        report["quarantined_workflow_count"] = len(children)
        if report["quarantined_workflow_count"] != 193:
            report.update(status="BLOCKED_INCOMPLETE_RECOVERY", reason="workflow count differs from recovery record")
            return report, 1
        missing = missing_dependencies()
        report["missing_dependencies"] = missing
        if missing:
            report.update(status="BLOCKED_MISSING_DEPENDENCIES", reason=", ".join(missing))
            return report, 2
        if (force_platform or sys.platform) != "win32":
            report.update(status="BLOCKED_NOT_WINDOWS", reason="Windows acceptance requires real Windows")
            return report, 2
        if preflight_only:
            report.update(status="READY_FOR_WINDOWS_SMOKE")
            return report, 0
        # Qt platform plugins can crash the interpreter: always isolate.
        env = os.environ.copy()
        env["PYTHONPATH"] = str(repo) + os.pathsep + env.get("PYTHONPATH", "")
        env["PYTHONUTF8"] = "1"
        env["QT_QPA_PLATFORM"] = "offscreen"  # automated screenshot, not manual screen approval
        p = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--_child", "--repo", str(repo),
                            "--out-dir", str(output)], cwd=repo, env=env, capture_output=True,
                           text=True, timeout=150, check=False)
        (output / "windows_smoke_stdout.txt").write_text(p.stdout + "\nSTDERR:\n" + p.stderr, encoding="utf-8")
        if p.returncode:
            report.update(status="FAILED_WINDOWS_SMOKE", reason="see windows_smoke_stdout.txt",
                          smoke_exit_code=p.returncode)
            return report, 1
        report.update(status="TECHNICAL_SMOKE_PASSED_VISUAL_REVIEW_PENDING",
                      smoke=json.loads(p.stdout))
        return report, 0
    except Exception as exc:
        report.update(status="FAILED_PRECHECK", reason=f"{type(exc).__name__}: {exc}")
        return report, 1


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo",type=Path,default=Path(__file__).resolve().parents[1])
    ap.add_argument("--out-dir",type=Path,default=Path("qa/windows"))
    ap.add_argument("--preflight-only",action="store_true")
    ap.add_argument("--_child",action="store_true",help=argparse.SUPPRESS)
    a=ap.parse_args()
    repo=a.repo.resolve(); out=a.out_dir.resolve()
    if a._child:
        try:
            print(json.dumps(smoke(repo, out), ensure_ascii=False))
            return 0
        except Exception:
            traceback.print_exc()
            return 1
    report,status=perform(repo,out,preflight_only=a.preflight_only)
    _atomic_json(out/"windows_acceptance.json",report)
    print(json.dumps({"status":report["status"], "exit_code":status,
                      "missing_dependencies":report.get("missing_dependencies",[]),
                      "report":str(out/"windows_acceptance.json")},ensure_ascii=False))
    return status

if __name__=="__main__":
    raise SystemExit(main())
