"""Local, isolated Git fixtures. No connection to GitHub or user repositories."""
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "compare_git_recovery.py"
spec = importlib.util.spec_from_file_location("compare_git_recovery", MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def cmd(repo, *args):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if r.returncode:
        raise AssertionError(r.stderr)
    return r.stdout


def init(repo, files):
    repo.mkdir()
    cmd(repo, "init", "-q", "-b", "main")
    cmd(repo, "config", "user.name", "QA")
    cmd(repo, "config", "user.email", "qa@example.invalid")
    for name, value in files.items():
        p = repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(value, encoding="utf-8")
    cmd(repo, "add", ".")
    cmd(repo, "commit", "-qm", "fixture")


class CompareRestoredGitTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.old = self.root / "old"
        self.new = self.root / "new"
        init(self.old, {"same.py": "print(1)\n", "different.py": "old\n", "only_old.txt": "a\n"})
        init(self.new, {"same.py": "print(1)\n", "different.py": "new\n", "only_new.txt": "b\n"})

    def tearDown(self):
        self.tmp.cleanup()

    def test_diff_counts(self):
        x = mod.compare(self.old, self.new, "refs/heads/main", "refs/heads/main")
        self.assertEqual(x["counts"], {"original_files": 3, "recovery_files": 3,
              "identical_blob_paths": 1, "changed_blob_paths": 1,
              "only_in_original": 1, "only_in_recovery": 1})
        self.assertEqual(x["only_in_original"], ["only_old.txt"])

    def test_identical_repos_rejected(self):
        with self.assertRaises(mod.RecoveryAuditError):
            mod.compare(self.old, self.old, "refs/heads/main", "refs/heads/main")

    def test_missing_ref_fails_closed(self):
        with self.assertRaises(mod.RecoveryAuditError):
            mod.compare(self.old, self.new, "refs/heads/does-not-exist", "refs/heads/main")

    def test_not_git_fails_closed(self):
        with self.assertRaises(mod.RecoveryAuditError):
            mod.compare(self.root, self.new, "refs/heads/main", "refs/heads/main")

    def test_reads_bare_git_mirror(self):
        bare = self.root / "old.git"
        p = subprocess.run(["git", "clone", "--mirror", str(self.old), str(bare)],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        result = mod.compare(bare, self.new, "refs/heads/main", "refs/heads/main")
        self.assertEqual(result["counts"]["only_in_original"], 1)

    def test_refs_pr_branches(self):
        cmd(self.old, "branch", "pr-481")
        result = mod.compare(self.old, self.new, "refs/heads/main", "refs/heads/main")
        self.assertIn("refs/heads/pr-481", result["original"]["branches"])

    def test_data_output_json_serializable(self):
        result = mod.compare(self.old, self.new, "refs/heads/main", "refs/heads/main")
        self.assertIsInstance(json.loads(json.dumps(result)), dict)

if __name__ == "__main__":
    unittest.main()