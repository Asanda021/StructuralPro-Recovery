"""Publish counts and hashes from actual Phase 6 JUnit files, never estimates."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import xml.etree.ElementTree as ET


def main(paths):
    reports = []
    missing = []
    for name in paths:
        path = Path(name)
        if not path.is_file():
            missing.append(name)
            continue
        raw = path.read_bytes()
        root = ET.fromstring(raw)
        cases = list(root.iter('testcase'))
        failed = sum(case.find('failure') is not None for case in cases)
        errors = sum(case.find('error') is not None for case in cases)
        skipped = sum(case.find('skipped') is not None for case in cases)
        reports.append(dict(file=name, sha256=hashlib.sha256(raw).hexdigest(),
            tests=len(cases), passed=len(cases)-failed-errors-skipped,
            failed=failed, errors=errors, skipped=skipped,
            failures=[dict(test=case.get('classname', '') + '::' + case.get('name', ''),
                detail='\n'.join(node.get('message', '') + '\n' + (node.text or '')[-2200:] for node in case
                    if node.tag in ('failure', 'error'))[-3200:])
                for case in cases if case.find('failure') is not None or case.find('error') is not None]))
    def git(ref):
        return subprocess.check_output(['git', 'rev-parse', ref], text=True).strip()
    evidence = dict(commit=git('HEAD'), tree=git('HEAD^{tree}'),
        tracked_worktree_clean=subprocess.run(['git', 'diff', '--quiet', 'HEAD']).returncode == 0,
        platform=platform.platform(), python=platform.python_version(),
        reports=reports, missing=missing,
        warning_count=None, warning_note='JUnit does not encode the pytest warning count; inspect the original job log.')
    log = Path('phase6-pytest.log')
    if log.is_file():
        output = log.read_text(encoding='utf-8', errors='replace')
        counts = re.findall(r'(\d+) warnings?\b', output)
        evidence['warning_count'] = int(counts[-1]) if counts else None
        evidence['warning_note'] = 'Count extracted from pytest output when available, not from JUnit.'
        evidence['pytest_log_sha256'] = hashlib.sha256(log.read_bytes()).hexdigest()
        evidence['pytest_log_tail'] = output[-12000:]
    Path('phase6-acceptance-summary.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    summary = '## Phase 6 acceptance evidence\n\n```json\n' + json.dumps(evidence, indent=2) + '\n```\n'
    print(summary)
    # Public run annotations remain inspectable when the web UI requires login
    # for raw logs/artifacts. Keep the diagnostic bounded to synthetic QA data.
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        diagnostics = [failure['test'] + '\n' + failure['detail']
            for report in reports for failure in report['failures']]
        if missing:
            diagnostics.append('Missing JUnit: ' + ', '.join(missing) + '\n' + evidence.get('pytest_log_tail', '')[-6000:])
        for diagnostic in diagnostics[:5]:
            escaped = diagnostic.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
            print('::error title=Phase 6 measured test diagnostic::' + escaped)
        for report in reports:
            print('::notice title=Phase 6 measured counts::' + json.dumps({
                key: report[key] for key in ('file', 'tests', 'passed', 'failed', 'errors', 'skipped', 'sha256')}))
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as output:
            output.write(summary)
    return 1 if missing or not reports or any(not r['tests'] for r in reports) else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
