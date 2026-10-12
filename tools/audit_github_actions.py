#!/usr/bin/env python3
"""Offline, read-only, fail-closed GitHub Actions binary-path auditor.

NO commands/workflows are executed. A source gate is NEVER evidence that
GitHub Environment reviewers/rulesets/secret scoping were configured.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml

ENV = 'binary-build-approval'
REPO = "github.repository == 'Asanda021/StructuralPro'"
REF = "github.ref == 'refs/heads/main'"
GUARDS = ("github.event_name == 'workflow_dispatch'", "github.actor == 'Asanda021'",
          'inputs.build_approved == true', REPO, REF)
BUILD = (
    ('pyinstaller', r'\b(?:pyinstaller|python\s+-m\s+PyInstaller)\b'),
    ('nuitka', r'\bnuitka\b'), ('cx_freeze', r'\bcx[_-]freeze\b'),
    ('dotnet_publish', r'\bdotnet\s+publish\b'), ('msbuild', r'\bmsbuild(?:\.exe)?\b'),
    ('wix', r'\b(?:candle\.exe|light\.exe|wix\s+build)\b'),
    ('inno_setup', r'\b(?:ISCC(?:\.exe)?|iscc\s+)\b'),
    ('nsis', r'\b(?:makensis(?:\.exe)?)\b'),
    ('gradle_package', r'\b(?:gradle|gradlew)(?:\.bat)?\s+[^\n]*?(?::[\w-]+:)?(?:assemble|bundle)[\w:]*\b'),
    ('electron_builder', r'\belectron-builder\b'),
    ('docker_build', r'\bdocker\s+(?:build|buildx\s+build)\b'),
    ('windows_packaging', r'\bbuild_windows(?:_edition)?\.ps1\b'),
    ('release', r'\bgh\s+release\s+(?:create|upload)\b'),
    ('gradle_wrapper_package', r'\b(?:\./)?gradlew(?:\.bat)?\s+[^\n]*?\b(?:assemble|bundle)[A-Za-z0-9:_-]*'),
    ('wix_msi', r'\b(?:heat|candle|light)\.exe\b'),
    ('native_publish', r'\b(?:cargo\s+build|go\s+build)\b'),
)
DELIVERY = (
    ('upload_artifact', r'actions/upload-artifact@'),
    ('github_release', r'softprops/action-gh-release@'),
    ('docker_publish', r'docker/(?:build-push-action|metadata-action)@'),
    ('github_release_cli', r'\bgh\s+release\s+(?:create|upload)\b'),
)
SCRIPT_REF = re.compile(r'(?:^|[\s"\'`])(?:\./|\$\{\{\s*github\.workspace\s*\}\}/)?'
                        r'((?:packaging|scripts|tools|\.github/actions)/[\w./-]+\.(?:ps1|sh|py|bat|cmd))\b', re.M)
LOCAL_ACTION = re.compile(r'^\./\.github/actions/([\w.-]+)$')
SUSPECT_SCRIPT = re.compile(r'(?i)(?:build|release|publish|package|installer|deploy|bundle|setup|compile)')
OPAQUE_INVOKE = re.compile(r'(?m)(?:^|[\s;&|])(?:\./|bash\s+|sh\s+|pwsh\s+|powershell\s+)[^\s;|]+\.(?:sh|ps1|bat|cmd)\b')


def text_matches(content: str, patterns: tuple[tuple[str, str], ...]) -> list[str]:
    return [name for name, pattern in patterns if re.search(pattern, content, re.I)]


def local_dependency(root: Path, candidate: str, visited: set[str], depth: int = 0) -> dict[str, Any]:
    """Read scripts/actions recursively only under root. Never execute them."""
    if depth > 12:
        return {'path': candidate, 'status': 'needs_review', 'reason': 'recursion_limit'}
    path = (root / candidate).resolve()
    if not path.is_relative_to(root.resolve()):
        return {'path': candidate, 'status': 'needs_review', 'reason': 'path_escape'}
    if candidate in visited:
        return {'path': candidate, 'status': 'cycle_or_already_seen'}
    visited.add(candidate)
    if not path.is_file():
        return {'path': candidate, 'status': 'needs_review', 'reason': 'not_available'}
    try:
        body = path.read_text(encoding='utf-8')
    except (UnicodeError, OSError):
        return {'path': candidate, 'status': 'needs_review', 'reason': 'unreadable'}
    if candidate.endswith(('.yml', '.yaml')):
        try:
            data = yaml.safe_load(body) or {}
            if isinstance(data, dict) and 'runs' in data:
                composite = data['runs'] or {}
                if composite.get('using') == 'composite':
                    body += '\n'.join(str(step.get('run', '')) + '\n' + str(step.get('uses', ''))
                                      for step in (composite.get('steps') or []) if isinstance(step, dict))
                else:
                    return {'path': candidate, 'status': 'needs_review', 'reason': 'opaque_action'}
        except yaml.YAMLError:
            return {'path': candidate, 'status': 'needs_review', 'reason': 'bad_yaml'}
    children = [local_dependency(root, m.group(1), visited, depth + 1) for m in SCRIPT_REF.finditer(body)]
    for act in re.finditer(r'uses:\s*(\./\.github/actions/[\w.-]+)', body):
        children.append(local_dependency(root, act.group(1)[2:] + '/action.yml', visited, depth + 1))
    return {'path': candidate, 'status': 'inspected', 'binary': text_matches(body, BUILD),
            'delivery': text_matches(body, DELIVERY), 'dependencies': children}


def binary_in_tree(nodes: list[dict]) -> bool:
    return any(bool(n.get('binary')) or binary_in_tree(n.get('dependencies', [])) for n in nodes)


def needs_review_in_tree(nodes: list[dict]) -> bool:
    return any(n.get('status') == 'needs_review' or needs_review_in_tree(n.get('dependencies', [])) for n in nodes)


def _event_names(raw: Any) -> list[str]:
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return sorted(map(str, raw))
    if isinstance(raw, dict):
        return sorted(str(k) for k in raw)
    return ['unknown']


def _job_gate(job: dict) -> dict[str, Any]:
    steps = job.get('steps') or []
    condition = str(job.get('if') or '')
    env = job.get('environment')
    name = env.get('name') if isinstance(env, dict) else env
    first = steps[0] if steps and isinstance(steps[0], dict) else {}
    shell = str(first.get('shell', ''))
    run = str(first.get('run', '')).strip()
    expected_secret = '${{ secrets.STRUCTURALPRO_BINARY_BUILD_APPROVAL }}'
    secret_ok = isinstance(first.get('env'), dict) and first['env'].get('STRUCTURALPRO_BUILD_PERMIT') == expected_secret
    preflight = (secret_ok and first.get('continue-on-error') not in (True, 'true')
                 and ((shell == 'bash' and run == 'test -n "$STRUCTURALPRO_BUILD_PERMIT"')
                      or (shell == 'pwsh' and run == "if (-not $env:STRUCTURALPRO_BUILD_PERMIT) { throw 'Missing protected owner build authorization' }")))
    expected_condition = '${{ ' + ' && '.join(GUARDS) + ' }}'
    return {'environment': name, 'job_condition': condition,
            'source_gate_present': name == ENV and condition.strip() == expected_condition
                                   and not job.get('continue-on-error') and preflight,
            'preflight_first': preflight,
            'requires_external_settings_verification': True}


def _publish_gate(job: dict) -> dict[str, Any]:
    """Check source policy only; cannot attest GitHub reviewer configuration."""
    steps = job.get('steps') or []
    first = steps[0] if steps and isinstance(steps[0], dict) else {}
    environment = job.get('environment')
    name = environment.get('name') if isinstance(environment, dict) else environment
    expected = '${{ ' + ' && '.join((
        "github.event_name == 'workflow_dispatch'", "github.actor == 'Asanda021'",
        REPO, REF, 'inputs.build_approved == true',
        'inputs.publish_approved == true')) + ' }}'
    preflight = (first.get('shell') == 'pwsh' and
                 first.get('env', {}).get('STRUCTURALPRO_PUBLISH_PERMIT') ==
                 '${{ secrets.STRUCTURALPRO_BINARY_PUBLISH_APPROVAL }}' and
                 str(first.get('run', '')).strip() ==
                 "if (-not $env:STRUCTURALPRO_PUBLISH_PERMIT) { throw 'Missing independent protected publish authorization' }" and
                 first.get('continue-on-error') not in (True, 'true'))
    return {'environment': name, 'source_gate_present':
            (name == 'binary-publish-approval' and job.get('needs') == 'deploy-production'
             and job.get('permissions') == {'contents': 'write'}
             and str(job.get('if', '')).strip() == expected
             and not job.get('continue-on-error') and preflight),
            'preflight_first': preflight,
            'requires_external_settings_verification': True}


def inspect(root: Path) -> dict[str, Any]:
    root = root.resolve()
    workflow_dir = root / '.github/workflows'
    if not workflow_dir.is_dir():
        raise FileNotFoundError(workflow_dir)
    files = sorted((*workflow_dir.glob('*.yml'), *workflow_dir.glob('*.yaml')))
    findings, parse_errors, inventory = [], [], []
    for file in files:
        relative = file.relative_to(root).as_posix()
        try:
            workflow = yaml.safe_load(file.read_text(encoding='utf-8')) or {}
            if not isinstance(workflow, dict) or not isinstance(workflow.get('jobs'), dict):
                raise ValueError('workflow does not contain jobs mapping')
        except (yaml.YAMLError, ValueError, UnicodeError) as exc:
            parse_errors.append({'workflow': relative, 'error': str(exc)})
            continue
        events = _event_names(workflow.get('on', workflow.get(True)))  # PyYAML 1.1 on: -> True
        manifest = {'path': relative, 'name': workflow.get('name', ''), 'events': events, 'jobs': []}
        inventory.append(manifest)
        for name, job in workflow['jobs'].items():
            if not isinstance(job, dict):
                parse_errors.append({'workflow': relative, 'job': name, 'error': 'non_mapping_job'})
                continue
            steps = job.get('steps') or []
            if not isinstance(steps, list):
                parse_errors.append({'workflow': relative, 'job': name, 'error': 'non_list_steps'})
                continue
            direct, delivery, deps, unknown = [], [], [], []
            # Reusable workflow jobs are outside caller step list; an uninspected call is never trusted.
            if 'uses' in job:
                unknown.append('reusable_workflow:' + str(job['uses']))
            for index, step in enumerate(steps):
                if not isinstance(step, dict):
                    unknown.append('unparseable_step')
                    continue
                contents = str(step.get('run', '')) + '\n' + str(step.get('uses', ''))
                direct.extend([{'step': index, 'kind': hit} for hit in text_matches(contents, BUILD)])
                delivery.extend([{'step': index, 'kind': hit} for hit in text_matches(contents, DELIVERY)])
                for match in SCRIPT_REF.finditer(contents):
                    deps.append(local_dependency(root, match.group(1), set()))
                action_match = LOCAL_ACTION.match(str(step.get('uses', '')))
                if action_match:
                    deps.append(local_dependency(root, '.github/actions/'+action_match.group(1)+'/action.yml', set()))
                elif step.get('uses') and not str(step['uses']).startswith('./'):
                    unknown.append('external_action:' + str(step['uses']))
                elif step.get('uses') and str(step['uses']).startswith('./') and not action_match:
                    unknown.append('local_action_other:' + str(step['uses']))
                if SUSPECT_SCRIPT.search(contents) and '${{' in contents and not direct:
                    unknown.append('dynamic_command_or_script')
                if OPAQUE_INVOKE.search(contents) and not SCRIPT_REF.search(contents):
                    unknown.append('unresolved_shell_script_invocation')
            is_build = bool(direct) or binary_in_tree(deps)
            review = bool(unknown) or needs_review_in_tree(deps)
            is_release = any(d['kind'] in ('github_release','github_release_cli') for d in delivery)
            gate = _publish_gate(job) if is_release and not is_build else _job_gate(job)
            manifest['jobs'].append({'name': str(name), 'binary_build': is_build,
                                     'build_commands': direct, 'delivery_actions': delivery,
                                     'script_dependencies': deps, 'unknown_or_external': unknown[:15],
                                     'source_gate': gate['source_gate_present'],
                                     'has_reusable_workflow': 'uses' in job})
            if is_build:
                classification = 'gated_in_source_unverified_settings' if gate['source_gate_present'] else 'unprotected_binary_job'
            elif is_release:
                classification = ('gated_publication_unverified_settings' if gate['source_gate_present']
                                  else 'unprotected_publication_job')
            elif delivery:
                classification = 'delivery_nonbinary_or_indeterminate_review_payload'
            elif review:
                classification = 'needs_review'
            else:
                continue  # ordinary jobs are counted in total_jobs below
            findings.append({'workflow': relative, 'job': str(name), 'events': events,
                             'classification': classification, 'build_commands': direct,
                             'delivery_actions': delivery, 'local_dependencies': deps,
                             'unknown_or_external': unknown[:15], 'gate': gate})
    all_jobs = 0
    for file in files:
        try:
            data = yaml.safe_load(file.read_text(encoding='utf-8')) or {}
            all_jobs += len(data.get('jobs') or {}) if isinstance(data, dict) else 0
        except (yaml.YAMLError, UnicodeError, ValueError):
            pass
    return {'workflow_count': len(files), 'parsed_workflow_count': len(inventory),
            'workflow_inventory': inventory,
            'total_jobs': all_jobs, 'findings_count': len(findings),
            'direct_or_indirect_binary_jobs': sum(f['classification'] in ('unprotected_binary_job','gated_in_source_unverified_settings') for f in findings),
            'unprotected_binary_jobs': sum(f['classification']=='unprotected_binary_job' for f in findings),
            'unprotected_publication_jobs': sum(f['classification']=='unprotected_publication_job' for f in findings),
            'parse_errors': parse_errors, 'findings': findings,
            'github_settings_verified': False, 'note': 'Read-only source evidence only; never executes any binary.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--strict', action='store_true', help='exit 2 on unprotected binaries/parse errors')
    args = parser.parse_args()
    report = inspect(args.repo)
    serialized = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    if args.output:
        args.output.write_text(serialized, encoding='utf-8')
    else:
        print(serialized)
    if args.strict and (report['unprotected_binary_jobs'] or report['unprotected_publication_jobs'] or report['parse_errors']
                        or any(item['classification'] == 'needs_review' for item in report['findings'])):
        raise SystemExit(2)


if __name__ == '__main__':
    main()
