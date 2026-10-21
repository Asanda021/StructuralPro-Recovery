"""Explicit, offline eight-roof acceptance runner. No Actions/build/release.

A successful legacy-core run is NEVER substituted for full HEAD acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
LEGACY_TESTS = (
    'tests/test_roof_specialist_work.py',
    'tests/test_waffle_specialist_work.py',
    'tests/test_hollowcore_specialist_work.py',
)
NEW_TESTS = (
    'tests/test_void_former_roofs_20261016.py',
    'tests/test_void_former_roof_ui_20261016.py',
)
OLD_UI_TESTS = (
    'tests/test_roof_specialist_ui.py',
    'tests/test_waffle_specialist_ui.py',
    'tests/test_hollowcore_specialist_ui.py',
)


def run() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('legacy-core', 'eight-roofs'), default='eight-roofs')
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--source-ref', required=True,
                        help='Exact verified source commit/archive SHA; not guessed')
    args = parser.parse_args()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    for previous in ('pytest.xml', 'pytest.log'):
        (out / previous).unlink(missing_ok=True)
    info = {
        'started_at_utc': datetime.now(timezone.utc).isoformat(),
        'source_ref_claim': args.source_ref,
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'mode': args.mode,
        'scope': 'archived six-roof math/SQLite only' if args.mode == 'legacy-core'
                 else 'full current eight-roof worktree',
        'tests_executed': False,
        'fully_accepted': False,
        'missing_dependencies': [],
        'blocking_reasons': [],
    }
    if args.mode == 'eight-roofs':
        if not re.fullmatch(r'[a-fA-F0-9]{40}', args.source_ref):
            info['blocking_reasons'].append('An exact 40-character Git SHA is required')
        actual_head = subprocess.run(
            ['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True, check=False,
        )
        if actual_head.returncode != 0 or actual_head.stdout.strip() != args.source_ref:
            info['blocking_reasons'].append('Checked-out Git HEAD differs from requested acceptance SHA')
        info['verified_git_head'] = actual_head.stdout.strip() if actual_head.returncode == 0 else None
        required = {'PySide6': 'PySide6', 'arabic_reshaper': 'arabic-reshaper',
                    'bidi': 'python-bidi'}
        info['missing_dependencies'] = [p for mod, p in required.items()
                                        if importlib.util.find_spec(mod) is None]
        missing = [f for f in LEGACY_TESTS + NEW_TESTS + OLD_UI_TESTS
                   if not (ROOT / f).is_file()]
        if missing:
            info['blocking_reasons'].append('Missing test modules: ' + ', '.join(missing))
        sys.path.insert(0, str(ROOT))
        try:
            from core.takeoff.roof_detail import KINDS, VOID_KINDS
        except (ImportError, AttributeError) as exc:
            KINDS, VOID_KINDS = (), ()
            info['blocking_reasons'].append('Missing specialist implementation: ' + str(exc))
        expected = {'solid_slab', 'joist_block', 'joist_foam',
                    'waffle_one_way', 'waffle_two_way', 'hollow_core_detail',
                    'uboot', 'cobiax'}
        if set(KINDS) != expected or set(VOID_KINDS) != {'uboot', 'cobiax'}:
            info['blocking_reasons'].append('Eight-kind specialist contract mismatch')
        if info['missing_dependencies']:
            info['blocking_reasons'].append('Missing modules: ' + ', '.join(info['missing_dependencies']))
        suites = LEGACY_TESTS + NEW_TESTS + OLD_UI_TESTS
        selection = []
    else:
        suites = LEGACY_TESTS
        # Excludes report & a named finance test which exports XLSX through Qt Jalali date.
        # The exclusion is intentional and always recorded in the receipt.
        selection = ['-k', 'not report and not real_detail_amendment']
        info['excluded_pytest_expression'] = selection[-1]
    if info['blocking_reasons']:
        info['exit_code'] = 2
        (out / 'receipt.json').write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding='utf-8')
        return 2
    junit = out / 'pytest.xml'
    command = [sys.executable, '-m', 'pytest', '-q', *suites, *selection,
               f'--junitxml={junit}', '--disable-warnings']
    info['command'] = command
    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join((str(ROOT), str(ROOT / 'tests'), env.get('PYTHONPATH', '')))
    completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
    info['tests_executed'] = True
    info['exit_code'] = completed.returncode
    (out / 'pytest.log').write_text(completed.stdout + '\n' + completed.stderr, encoding='utf-8')
    if junit.exists():
        root = ElementTree.parse(junit).getroot()
        suite = root.find('testsuite') if root.tag == 'testsuites' else root
        info['junit'] = {key: suite.attrib.get(key) for key in ('tests', 'failures', 'errors', 'skipped')}
    info['fully_accepted'] = False  # Windows, real engineering review and owner acceptance separate.
    (out / 'receipt.json').write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding='utf-8')
    return completed.returncode


if __name__ == '__main__':
    raise SystemExit(run())
