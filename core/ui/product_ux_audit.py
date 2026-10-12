"""P28 — deterministic Product UX Master Audit.

The audit inspects the existing desktop UX contracts without importing Qt or
changing engineering/calculation behavior. It is intentionally fail-closed:
unknown or missing UX evidence is reported as a failed criterion.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class UXAuditCheck:
    key: str
    passed: bool
    evidence: str


@dataclass(frozen=True)
class UXAuditReport:
    checks: tuple[UXAuditCheck, ...]

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(c.passed for c in self.checks)

    @property
    def failed(self) -> tuple[UXAuditCheck, ...]:
        return tuple(c for c in self.checks if not c.passed)

    def as_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "checks": [
                {"key": c.key, "passed": c.passed, "evidence": c.evidence}
                for c in self.checks
            ],
        }


def _text(path: str) -> str:
    candidate = ROOT / path
    return candidate.read_text(encoding="utf-8") if candidate.exists() else ""


def run_product_ux_audit() -> UXAuditReport:
    ux = _text("core/ui/ux.py")
    theme = _text("app/theme.py")
    main = _text("app/main.py")
    tests = _text("tests/test_ui_design_system.py")
    graphical = _text("app/graphical_takeoff.py")

    checks = (
        UXAuditCheck(
            "navigation",
            "def navigation_groups" in ux
            and all(marker in ux for marker in ("شروع", "متره و برآورد", "مدیریت پروژه", "سیستم")),
            "Grouped desktop navigation contract exists.",
        ),
        UXAuditCheck(
            "global_actions",
            all(marker in ux for marker in ("Ctrl+N", "Ctrl+O", "Ctrl+S", "Ctrl+K", "F1")),
            "Core global actions expose deterministic shortcuts.",
        ),
        UXAuditCheck(
            "rtl",
            "setLayoutDirection(Qt.LayoutDirection.RightToLeft)" in main,
            "Desktop shell explicitly enables RTL.",
        ),
        UXAuditCheck(
            "accessibility",
            "QToolTip" in theme
            and "#NavigationPanel" in theme
            and ":focus" in theme
            and "disabled" in theme,
            "Theme contains tooltip, navigation, focus and disabled-state contracts.",
        ),
        UXAuditCheck(
            "visual_tokens",
            all(token in theme for token in ("#PrimaryAction", "#SecondaryAction", "#KpiCard", "#PageTitle", "#NavButton")),
            "Commercial visual tokens are present.",
        ),
        UXAuditCheck(
            "takeoff_surface",
            Path(ROOT / "app/graphical_takeoff.py").exists()
            and "graphical" in graphical.lower(),
            "Drawing/takeoff desktop surface exists.",
        ),
        UXAuditCheck(
            "functional_quality_gate",
            "service.validate_project_data(project_id)" in main
            and "🟢 کنترل ساختار پروژه" not in main,
            "Quality control is backed by service validation, not hard-coded green state.",
        ),
        UXAuditCheck(
            "regression_contract",
            "test_commercial_ui_design_tokens_exist" in tests
            and "test_priority8_rtl_and_accessibility_tokens" in tests,
            "Existing UX regression suite is discoverable.",
        ),
    )
    return UXAuditReport(checks)


def assert_product_ux_audit() -> UXAuditReport:
    report = run_product_ux_audit()
    if not report.passed:
        failed = ", ".join(check.key for check in report.failed)
        raise AssertionError(f"P28 Product UX Master Audit failed: {failed}")
    return report
