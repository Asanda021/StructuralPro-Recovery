"""Portable static tests for PR #462. No build commands are executed."""
from __future__ import annotations
import copy
import importlib.util
from pathlib import Path
from tests.historical_contracts import historical_root

HISTORY = historical_root()  # Isolated historical contract, never active Actions.

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCANNER = ROOT / 'tools' / 'audit_github_actions.py'
spec = importlib.util.spec_from_file_location('structuralpro_ci_binary_audit', SCANNER)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def workflow(relative):
    with (HISTORY / '.github/workflows' / relative).open(encoding='utf8') as stream:
        return yaml.safe_load(stream)


def test_mobile_contract_automatic_and_android_binary_manual():
    data = workflow('priority-611-620-mobile-clients.yml')
    events = audit._event_names(data.get('on', data.get(True)))
    assert 'push' in events and 'pull_request' in events
    assert 'workflow_dispatch' in events
    assert 'pytest -q tests/test_p611_p620_mobile_clients.py' in str(data['jobs']['contract'])
    assert 'assemble' not in str(data['jobs']['contract'])
    android = data['jobs']['android']
    assert audit._job_gate(android)['source_gate_present']
    assert 'gradle :app:assembleDebug' in str(android['steps'][-1])
    assert 'checkout' in str(android['steps'][1])


def test_p37_disables_all_automatic_release_and_build_triggers():
    data = workflow('p37-real-product-deployment.yml')
    assert audit._event_names(data.get('on', data.get(True))) == ['workflow_dispatch']
    job = data['jobs']['deploy-production']
    assert audit._job_gate(job)['source_gate_present']
    contents = str(job['steps'])
    for marker in ('build_windows.ps1','windows_installer_smoke.ps1','upload-artifact@v4'):
        assert marker in contents, marker
    assert 'action-gh-release@v2' not in contents
    publisher = data['jobs']['publish-release']
    assert audit._publish_gate(publisher)['source_gate_present']
    assert 'action-gh-release@v2' in str(publisher['steps'])
    # Publication is a separate, independently protected job.
    assert not any(isinstance(s, dict) and s.get('continue-on-error') for s in job['steps'])


def test_p100_owner_main_only_with_isolated_publish_permissions():
    data = workflow('p100-pricebook-archive-sync.yml')
    assert audit._event_names(data.get('on', data.get(True))) == ['workflow_dispatch']
    assert data['permissions'] == {'contents': 'read'}
    sync = data['jobs']['sync']
    publish = data['jobs']['publish']
    guard = "${{ github.event_name == 'workflow_dispatch' && github.actor == 'Asanda021' && github.repository == 'Asanda021/StructuralPro' && github.ref == 'refs/heads/main' }}"
    assert sync['if'] == guard and publish['if'] == guard
    assert sync['permissions'] == {'contents': 'read'}
    assert publish['permissions'] == {'contents': 'write', 'pull-requests': 'write'}
    assert publish['needs'] == 'sync'
    assert 'GITHUB_TOKEN' not in sync.get('env', {})
    assert all('GITHUB_TOKEN' not in step.get('env', {}) for step in sync['steps'])
    for job in (sync, publish):
        checkout = next(step for step in job['steps'] if step.get('uses') == 'actions/checkout@v4')
        assert checkout['with'] == {'ref': 'refs/heads/main', 'persist-credentials': False}
    upload = next(step for step in sync['steps'] if step.get('uses') == 'actions/upload-artifact@v4')
    download = next(step for step in publish['steps'] if step.get('uses') == 'actions/download-artifact@v4')
    assert upload['with']['name'] == download['with']['name'] == 'p100-verified-pricebooks'
    assert upload['with']['if-no-files-found'] == 'error'
    assert 'data/pricebooks/' == download['with']['path']
    publisher = next(step for step in publish['steps'] if step.get('name') == 'Publish imported pricebooks on automation branch')
    assert publisher['env']['GITHUB_TOKEN'] == '${{ secrets.GITHUB_TOKEN }}'
    assert 'git -c "http.https://github.com/.extraheader=AUTHORIZATION: basic $token_header" push' in publisher['run']
    assert not any('sync_pricebooks_24.py' in str(step) for step in publish['steps'])


@pytest.mark.parametrize('bad', [
    lambda j: j.update({'if': "${{ github.event_name == 'push' }}"}),
    lambda j: j.update({'if': j['if'].replace(' }}',' || true }}')}),
    lambda j: j.update({'if': j['if'].replace('refs/heads/main','refs/tags/v1')}),
    lambda j: j.update({'if': j['if'].replace('Asanda021/StructuralPro','attacker/fork')}),
    lambda j: j.update({'environment': {'name':'unprotected'}}),
    lambda j: j.pop('environment'),
    lambda j: j['steps'].pop(0),
    lambda j: j['steps'][0].update({'run':'test -n "$STRUCTURALPRO_BUILD_PERMIT" || true'}),
    lambda j: j['steps'][0].update({'continue-on-error':True}),
    lambda j: j['steps'][0].update({'env': {'STRUCTURALPRO_BUILD_PERMIT':'${{ inputs.build_approved }}'}}),
])
def test_mutated_android_policy_must_fail_closed(bad):
    job = copy.deepcopy(workflow('priority-611-620-mobile-clients.yml')['jobs']['android'])
    bad(job)
    assert not audit._job_gate(job)['source_gate_present']


@pytest.mark.parametrize('event,actor,approved,ref,repo,secret,external_review', [
    ('push','Asanda021',True,'refs/heads/main','Asanda021/StructuralPro',True,True),
    ('pull_request','Asanda021',True,'refs/heads/main','Asanda021/StructuralPro',True,True),
    ('release','Asanda021',True,'refs/heads/main','Asanda021/StructuralPro',True,True),
    ('workflow_dispatch','Asanda021',False,'refs/heads/main','Asanda021/StructuralPro',True,True),
    ('workflow_dispatch','Asanda021',True,'refs/tags/v1','Asanda021/StructuralPro',True,True),
    ('workflow_dispatch','Asanda021',True,'refs/heads/main','attacker/fork',True,True),
    ('workflow_dispatch','Asanda021',True,'refs/heads/main','Asanda021/StructuralPro',False,True),
    ('workflow_dispatch','Asanda021',True,'refs/heads/main','Asanda021/StructuralPro',True,False),
])
def test_mock_authorization_denies_invalid_requests(event,actor,approved,ref,repo,secret,external_review):
    # Mock of intended policy only. Real GitHub required reviewers NOT verified here.
    allowed = (event == 'workflow_dispatch' and actor == 'Asanda021' and approved is True
               and ref == 'refs/heads/main' and repo == 'Asanda021/StructuralPro'
               and secret and external_review)
    assert allowed is False


def test_indirect_build_script_is_caught(tmp_path):
    wf = tmp_path / '.github/workflows/indirect.yml'; wf.parent.mkdir(parents=True)
    wf.write_text('name: indirect\non: {push: {}}\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: ./packaging/helper.sh\n')
    script = tmp_path / 'packaging/helper.sh'; script.parent.mkdir()
    script.write_text('python -m PyInstaller project.py\n')
    report = audit.inspect(tmp_path)
    assert report['unprotected_binary_jobs'] == 1
    assert report['github_settings_verified'] is False


def test_reusable_workflow_needs_review_not_certified(tmp_path):
    wf = tmp_path / '.github/workflows/reusable.yml'; wf.parent.mkdir(parents=True)
    wf.write_text('name: delegated\non: {push: {}}\njobs:\n  call:\n    uses: ./.github/workflows/build.yml\n')
    report = audit.inspect(tmp_path)
    assert report['findings'][0]['classification']=='needs_review'


def test_upload_without_identified_build_is_reviewed_not_assumed_binary(tmp_path):
    wf = tmp_path / '.github/workflows/report.yml'; wf.parent.mkdir(parents=True)
    wf.write_text('name: report\non: {pull_request: {}}\njobs:\n  report:\n    runs-on: ubuntu-latest\n    steps:\n      - run: python -m pytest -q\n      - uses: actions/upload-artifact@v4\n')
    report=audit.inspect(tmp_path)
    assert report['direct_or_indirect_binary_jobs']==0
    assert 'review_payload' in report['findings'][0]['classification']


def test_local_guard_presence_never_proves_actual_github_environment():
    assert audit.inspect(HISTORY)['github_settings_verified'] is False
