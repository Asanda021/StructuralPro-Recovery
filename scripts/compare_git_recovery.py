"""Read-only comparison of StructuralPro's *restored original* Git history vs recovery.

No network calls, no fetch/push/merge/rebase, no Git-object writes.
Writes only the requested JSON report outside the Git repositories.

Usage:
 python scripts/compare_git_recovery.py --original PATH --recovery PATH \
     --output /path/to/comparison.json

Both repositories must be valid local Git repositories (bare mirrors work).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


class RecoveryAuditError(RuntimeError):
    """Refuse to compare when inputs cannot be safely verified."""


def git(repo: Path, *args: str) -> bytes:
    p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=False)
    if p.returncode != 0:
        raise RecoveryAuditError(
            f"Git read failed in {repo.name} ({' '.join(args)}): "
            + p.stderr.decode("utf-8", errors="replace").strip()[:500]
        )
    return p.stdout


def refs(repo: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in git(repo, "show-ref").decode("utf-8", errors="replace").splitlines():
        sha, name = line.split(" ", 1)
        out[name] = sha
    return out


def blobs(repo: Path, revision: str) -> dict[str, str]:
    result: dict[str, str] = {}
    data = git(repo, "ls-tree", "--full-tree", "-r", "-z", revision)
    for entry in data.split(b"\0"):
        if not entry:
            continue
        try:
            meta, raw_path = entry.split(b"\t", 1)
            mode, kind, blobsha = meta.decode("ascii").split(" ", 2)
            if kind != "blob":
                continue  # no submodules treated as source code
            path = raw_path.decode("utf-8", errors="surrogateescape")
            result[path] = blobsha
        except (ValueError, UnicodeError) as ex:
            raise RecoveryAuditError("Malformed Git tree entry; refused comparison") from ex
    return result


def inspect(repo: Path, revision: str) -> dict:
    if not repo.exists():
        raise RecoveryAuditError(f"Repository not found: {repo}")
    git(repo, "rev-parse", "--git-dir")
    object_format = git(repo, "rev-parse", "--show-object-format").decode().strip()
    head = git(repo, "rev-parse", "--verify", revision + "^{commit}").decode().strip()
    all_refs = refs(repo)
    count = int(git(repo, "rev-list", "--all", "--count").strip())
    return {
        "revision": revision,
        "head_commit": head,
        "git_object_format": object_format,
        "commits_reachable_all_refs": count,
        "branches": sorted(r for r in all_refs if r.startswith("refs/heads/")),
        "tags": sorted(r for r in all_refs if r.startswith("refs/tags/")),
        "pull_refs": sorted(r for r in all_refs if r.startswith("refs/pull/")),
        "blobs": blobs(repo, revision),
    }


def compare(original: Path, recovery: Path, original_ref: str, recovery_ref: str) -> dict:
    if original.resolve() == recovery.resolve():
        raise RecoveryAuditError("Original and recovery inputs are the same directory")
    old = inspect(original, original_ref)
    new = inspect(recovery, recovery_ref)
    if old["git_object_format"] != new["git_object_format"]:
        raise RecoveryAuditError("Git object hash formats differ; direct blob SHA comparison unsafe")
    old_files, new_files = old.pop("blobs"), new.pop("blobs")
    common = set(old_files) & set(new_files)
    same = [x for x in common if old_files[x] == new_files[x]]
    changed = [x for x in common if old_files[x] != new_files[x]]
    missing = sorted(set(old_files) - set(new_files))
    recovery_only = sorted(set(new_files) - set(old_files))
    return {
        "result_type": "read_only_git_tree_comparison",
        "warning": "Diff shows tree differences, not proof of which PR is complete. Quarantined workflows may appear as moved files.",
        "original": old,
        "recovery": new,
        "counts": {
            "original_files": len(old_files),
            "recovery_files": len(new_files),
            "identical_blob_paths": len(same),
            "changed_blob_paths": len(changed),
            "only_in_original": len(missing),
            "only_in_recovery": len(recovery_only),
        },
        "changed": sorted(changed),
        "only_in_original": missing,
        "only_in_recovery": recovery_only,
        "historical_refs_prs_462_464_467_468_481": [
            r for r in old["pull_refs"] if any(r.startswith(f"refs/pull/{n}/") for n in (462, 464, 467, 468, 481))
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", required=True, type=Path)
    parser.add_argument("--recovery", required=True, type=Path)
    parser.add_argument("--original-ref", default="refs/heads/main")
    parser.add_argument("--recovery-ref", default="refs/heads/main")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        out = compare(args.original, args.recovery, args.original_ref, args.recovery_ref)
        target = args.output.resolve()
        if target.is_relative_to(args.original.resolve()) or target.is_relative_to(args.recovery.resolve()):
            raise RecoveryAuditError("Output must be outside both Git repository folders")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("SAFE_READ_ONLY_GIT_COMPARISON_OK")
        print(json.dumps(out["counts"], ensure_ascii=False))
        print("Report:", target)
        return 0
    except (RecoveryAuditError, OSError) as ex:
        print("FAIL_CLOSED:", ex, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())