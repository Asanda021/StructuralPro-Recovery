"""Fail-closed static checks only; intentionally never executes GitHub Actions."""
from pathlib import Path
from tests.historical_contracts import historical_root

HISTORY = historical_root()  # Isolated historical contract, never active Actions.
import copy
import pytest
import yaml

ROOT=Path(__file__).resolve().parents[1]
P=HISTORY/'.github/workflows/p37-real-product-deployment.yml'

def spec():
    return yaml.safe_load(P.read_text(encoding='utf8'))

def gate(job, *, publish=False):
    cond=str(job.get('if',''))
    required=["github.event_name == 'workflow_dispatch'", "github.actor == 'Asanda021'",
              "github.repository == 'Asanda021/StructuralPro'", "github.ref == 'refs/heads/main'",
              'inputs.build_approved == true']
    if publish: required.append('inputs.publish_approved == true')
    expected_env='binary-publish-approval' if publish else 'binary-build-approval'
    expected_secret='secrets.STRUCTURALPRO_BINARY_PUBLISH_APPROVAL' if publish else 'secrets.STRUCTURALPRO_BINARY_BUILD_APPROVAL'
    first=job.get('steps',[{}])[0]
    return (all(x in cond for x in required)
            and job.get('environment',{}).get('name')==expected_env
            and expected_secret in str(first.get('env',{}))
            and 'if (-not $env:STRUCTURALPRO_' in str(first.get('run','')))

def test_build_and_release_jobs_separate():
    d=spec(); jobs=d['jobs']
    assert d['permissions']=={'contents':'read'}
    assert set(jobs)=={'deploy-production','publish-release'}
    assert gate(jobs['deploy-production'])
    assert jobs['deploy-production'].get('permissions',{}).get('contents','read')!='write'
    assert jobs['publish-release']['permissions']=={'contents':'write'}
    assert jobs['publish-release']['needs']=='deploy-production'
    assert gate(jobs['publish-release'],publish=True)
    assert 'softprops/action-gh-release@v2' not in str(jobs['deploy-production'])
    assert sum('softprops/action-gh-release@v2' in str(step) for step in jobs['publish-release']['steps'])==1

def test_unapproved_release_default_false():
    d=spec()
    events=d.get('on', d.get(True))
    assert events['workflow_dispatch']['inputs']['build_approved']['default'] is False
    assert events['workflow_dispatch']['inputs']['publish_approved']['default'] is False
    assert set(events)=={'workflow_dispatch'}

def test_release_artifact_bound_to_same_run_and_validated_before_publish():
    j=spec()['jobs']['publish-release']
    assert 'actions/download-artifact@v4' in str(j['steps'][1])
    assert "${{ github.run_id }}" in str(j['steps'][1])
    assert 'Get-FileHash' in str(j['steps'][2])
    assert 'inputs.release_version' in str(j['steps'][2])
    assert 'softprops/action-gh-release@v2' in str(j['steps'][3])

@pytest.mark.parametrize('mutation',[
    lambda j:j.update({'if':"${{ github.event_name == 'push' }}"}),
    lambda j:j.update({'if':str(j['if']).replace('inputs.publish_approved == true','inputs.publish_approved != true')}),
    lambda j:j.update({'if':str(j['if']).replace("github.actor == 'Asanda021'",'true')}),
    lambda j:j.update({'if':str(j['if']).replace('refs/heads/main','refs/heads/feature')}),
    lambda j:j.update({'if':str(j['if']).replace('Asanda021/StructuralPro','attacker/fork')}),
    lambda j:j.pop('environment'),
    lambda j:j.update({'environment':{'name':'unprotected'}}),
    lambda j:j['steps'].pop(0),
    lambda j:j['steps'][0].update({'env':{}}),
    lambda j:j.update({'if':'true'}),
])
def test_publish_mutations_rejected(mutation):
    job=copy.deepcopy(spec()['jobs']['publish-release'])
    mutation(job)
    assert not gate(job,publish=True)


def test_release_version_is_not_interpolated_into_powershell_source():
    for name,job_name in [('p37-real-product-deployment.yml','deploy-production'),
                          ('windows-release.yml','build-windows')]:
        data=yaml.safe_load((HISTORY/'.github/workflows'/name).read_text(encoding='utf8'))
        steps=data['jobs'][job_name]['steps']
        step=next(x for x in steps if x.get('name') in ('Validate release version','Validate version'))
        assert step['env']['REQUESTED_RELEASE_VERSION']=='${{ inputs.release_version }}'
        assert '${{ inputs.release_version }}' not in str(step['run'])
        assert '$requested=$env:REQUESTED_RELEASE_VERSION' in step['run']

@pytest.mark.parametrize('remove', [
    'condition', 'environment','secret','needs','write_permission','preflight','publish_approval',
])
def test_auditor_marks_mutated_publication_unprotected(tmp_path, remove):
    import sys
    sys.path.insert(0,str(ROOT/'tools'))
    from audit_github_actions import inspect
    d=spec()
    pub=d['jobs']['publish-release']
    if remove=='condition':pub['if']="${{ github.event_name == 'push' }}"
    elif remove=='environment':pub.pop('environment')
    elif remove=='secret':pub['steps'][0]['env']={}
    elif remove=='needs':pub.pop('needs')
    elif remove=='write_permission':pub['permissions']={'contents':'read'}
    elif remove=='preflight':pub['steps'][0]['run']='echo no auth'
    elif remove=='publish_approval':pub['if']=pub['if'].replace('inputs.publish_approved == true','true')
    path=tmp_path/'.github/workflows/p37.yml'
    path.parent.mkdir(parents=True)
    path.write_text(yaml.safe_dump(d,sort_keys=False),encoding='utf8')
    findings=inspect(tmp_path)['findings']
    assert any(x['job']=='publish-release' and x['classification']=='unprotected_publication_job' for x in findings)
