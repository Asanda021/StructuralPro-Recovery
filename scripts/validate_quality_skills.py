#!/usr/bin/env python3
"""Validate project quality skills and their byte-identical Claude/Codex mirrors.

Offline, stdlib-only, read-only. Does not validate StructuralPro source or tests.
"""
from pathlib import Path
import sys

SKILLS = (
    "structuralpro-architecture-auditor",
    "structuralpro-engineering-validator",
    "structuralpro-release-gatekeeper",
)


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    for name in SKILLS:
        codex = root / ".agents" / "skills" / name / "SKILL.md"
        claude = root / ".claude" / "skills" / name / "SKILL.md"
        if not codex.is_file() or not claude.is_file():
            errors.append(f"{name}: missing Claude or Codex file")
            continue
        if codex.read_bytes() != claude.read_bytes():
            errors.append(f"{name}: mirrors differ")
        content = codex.read_text(encoding="utf-8")
        if not content.startswith("---\n"):
            errors.append(f"{name}: missing frontmatter")
            continue
        try:
            front = content.split("---\n", 2)[1]
        except IndexError:
            errors.append(f"{name}: invalid frontmatter")
            continue
        if f"name: {name}" not in front:
            errors.append(f"{name}: name mismatch")
        if not any(line.startswith("description: ") and len(line)>45 for line in front.splitlines()):
            errors.append(f"{name}: meaningful description missing")
        for guard in ("NO_MERGE", "NO_MAIN_WRITE", "NO_EXE", "NO_INSTALLER", "NO_RELEASE"):
            if guard not in content:
                errors.append(f"{name}: missing explicit guard {guard}")
        if len(content) < 1000:
            errors.append(f"{name}: unexpectedly short")
    for p in ("docs/quality/QUALITY_AUDIT_CONTRACT_FA.md", "docs/quality/QUALITY_SKILLS_README_FA.md"):
        if not (root / p).is_file():
            errors.append(f"missing {p}")
    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    problems = validate(root)
    if problems:
        print("FAIL: " + "; ".join(problems), file=sys.stderr)
        return 1
    print(f"PASS: {len(SKILLS)} mirrored skills, metadata and guards valid; instruction-only validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
