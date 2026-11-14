from datetime import date, timedelta

import pytest

from core.projects.precedence_model import calculate_precedence
from core.projects.scheduling import cpm


START = '2027-03-20'
ALL = {'weekdays': list(range(7)), 'holidays': []}
WEEK = {'weekdays': [0, 1, 2, 3, 4], 'holidays': []}


def edge(a, b, kind='FS', lag=0):
    return {'pred': a, 'succ': b, 'type': kind, 'lag': lag}


def task(id, duration, **fields):
    return {'id': id, 'duration': duration, **fields}


def test_driving_graph_uses_tight_edges_and_preserves_tied_finishes():
    tasks = [task('A', 2), task('B', 2), task('C', 2), task('D', 4), task('M', 0)]
    links = [edge('A', 'B'), edge('A', 'C'), edge('B', 'M'), edge('C', 'M'),
             edge('B', 'C', 'SS', -1)]
    result = cpm(tasks, links, start=START, calendar=ALL)
    assert result['critical_ids'] == ['A', 'B', 'C', 'D', 'M']
    driving = result['driving']
    assert driving['finish_ids'] == ['B', 'C', 'D', 'M']
    assert set(map(tuple, driving['paths'])) == {
        ('A', 'B'), ('A', 'C'), ('D',), ('A', 'B', 'M'), ('A', 'C', 'M'),
    }
    assert ('B', 'C') not in {(x['pred'], x['succ']) for x in driving['edges']}
    assert driving['path_count'] == 5 and not driving['paths_truncated']


def test_driving_respects_explicit_date_and_generalized_links():
    tasks = [task('A', 5), task('B', 2, not_before='2027-03-24'), task('M', 0)]
    links = [edge('A', 'B', 'FF', -1), edge('B', 'M', 'SF', 3)]
    result = cpm(tasks, links, start=START, calendar=ALL)
    assert result['finish_boundary'] == '2027-03-27'
    assert result['driving']['paths'] == [['B', 'M']]
    assert result['driving']['roots'] == [{'id': 'B', 'reason': 'NOT_BEFORE'}]


def test_driving_path_count_is_bounded_with_full_graph_and_order_invariance():
    ids = ['A'] + [f'{i:02d}{side}' for i in range(16) for side in 'LR'] + ['Z']
    layers = [['A']] + [ids[1 + i * 2:3 + i * 2] for i in range(16)] + [['Z']]
    links = [edge(a, b) for left, right in zip(layers, layers[1:]) for a in left for b in right]
    tasks = [task(i, 1) for i in ids]
    first = cpm(tasks, links, start=START, calendar=ALL)
    second = cpm(list(reversed(tasks)), list(reversed(links)), start='2027-03-21', calendar=ALL)
    assert first['duration'] == second['duration'] == 18
    assert first['driving'] == second['driving']
    assert first['driving']['path_count'] == 2 ** 16
    assert first['driving']['paths_truncated']
    assert len(first['driving']['paths']) < 2 ** 16
    assert len(first['driving']['edges']) == len(links)
    assert date.fromisoformat(second['finish_boundary']) - date.fromisoformat(first['finish_boundary']) == timedelta(days=1)


def test_shared_day_offset_and_calendar_publish_same_driving_dag():
    tasks = [task('A', 2), task('B', 3), task('C', 1)]
    links = [edge('A', 'B', 'SS', 1), edge('A', 'C', 'FS', -1)]
    plan = {'tasks': [
        {'id': t['id'], 'duration_days': t['duration'],
         'predecessors': [e['pred'] for e in links if e['succ'] == t['id']],
         'links': [{'predecessor': e['pred'], 'type': e['type'], 'lag_days': e['lag']}
                   for e in links if e['succ'] == t['id']]}
        for t in tasks
    ]}
    result = calculate_precedence(plan, include_cpm=True)
    assert result['driving']['paths'] == [['A', 'B']]
    assert result['driving'] == cpm(tasks, links, start=START, calendar=ALL)['driving']
    calculate_precedence(plan)
    assert 'driving' not in plan

def test_activity_crew_equipment_intersection_uses_civil_finish_and_activity_float():
    calendars = {
        'six': {'weekdays': [0, 1, 2, 3, 4, 5], 'holidays': []},
        'crew': {'weekdays': [0, 1, 2, 3, 4], 'holidays': ['2027-03-23']},
        'lift': {'weekdays': [0, 1, 2, 3, 4], 'holidays': ['2027-03-24']},
    }
    tasks = [task('A', 2, calendar_id='six', resource_ids=['C', 'L']), task('B', 1), task('X', 1)]
    kwargs = {'start': START, 'calendar': ALL, 'calendars': calendars,
              'resource_calendars': {'C': 'crew', 'L': 'lift'}}
    result = cpm(tasks, [edge('A', 'B')], **kwargs)
    a, b, x = [result['activities'][key] for key in ('A', 'B', 'X')]
    assert (a['start'], a['finish'], a['finish_boundary']) == ('2027-03-22', '2027-03-25', '2027-03-26')
    assert (b['start'], b['finish'], result['finish_boundary']) == ('2027-03-26', '2027-03-26', '2027-03-27')
    assert (x['total_float'], x['free_float']) == (6, 6)
    assert result['driving']['paths'] == [['A', 'B']]
    assert result['offset_unit'] == 'CALENDAR_DAY' and a['float_unit'] == 'ACTIVITY_WORKDAY'
    calendars['crew']['holidays'].clear()
    revised = cpm(tasks, [edge('A', 'B')], **kwargs)
    assert revised['finish_boundary'] == '2027-03-25'
    assert revised['activities']['X']['total_float'] == 4


def test_slack_finish_relation_is_not_driving_at_the_calendar_origin():
    result=cpm([task('A',1,calendar_id='all'),task('B',3)],[edge('A','B','FF')],
               start=START,calendar=ALL,calendars={'all':ALL})
    assert result['finish_boundary']=='2027-03-23'
    assert result['driving']['paths']==[['B']]
    assert result['driving']['edges']==[]


def test_long_positive_lag_does_not_overflow_a_feasible_backward_pass():
    result=cpm([task('A',0,calendar_id='all'),task('B',1),task('C',90000)],
               [edge('A','B','FS',60000)],start=START,calendar=ALL,calendars={'all':ALL})
    assert result['duration']==90000
    assert result['activities']['A']['ls']==29999


def test_negative_lag_does_not_move_an_event_past_its_unshifted_date():
    result=cpm([task('A',1,calendar_id='all',not_before='2027-03-21'),task('B',1,calendar_id='all')],
               [edge('A','B','SS',-1)],start=START,calendar=WEEK,calendars={'all':ALL})
    assert result['activities']['B']['start']=='2027-03-20'


def test_initial_status_reuses_shared_workday_finish_across_weekend(recorded):
    from test_phase4_structure import cmd
    service,_,_=recorded
    start='2027-03-26'
    cmd(service,'schedule_calendar',start=start,calendar=WEEK)
    cmd(service,'schedule_activity',id='A',duration=1,relationships=[])
    cmd(service,'schedule_activity',id='B',duration=3,relationships=[edge('A','B','FF')])
    before=service.project_schedule('P')
    cmd(service,'schedule_status',data_date=start,policy='RETAINED_LOGIC',unreported='NOT_STARTED',observations=[])
    forecast=service.project_schedule_forecast('P')
    assert before['finish_boundary']==forecast['finish_boundary']=='2027-03-31'
    assert forecast['driving']['paths']==[['B']]


@pytest.mark.parametrize('kind,lag,expected', [
    ('FS', 0, '2027-03-24'), ('FS', 1, '2027-03-25'), ('SS', -1, '2027-03-21'),
    ('FF', 0, '2027-03-23'), ('SF', 2, '2027-03-23'),
])
def test_calendar_relationships_use_explicit_event_bounds(kind, lag, expected):
    tasks = [task('A', 2, calendar_id='week'), task('B', 1)]
    result = cpm(tasks, [edge('A', 'B', kind, lag)], start=START, calendar=ALL, calendars={'week': WEEK})
    assert result['activities']['B']['start'] == expected


@pytest.mark.parametrize('key,override', [
    ('missing', {}), ('week', {'shift_hours': 4}), ('week', {'weekdays': [0, '0']}),
    ('week', {'working_exceptions': ['2027-03-21'], 'holidays': ['2027-03-21']}),
])
def test_invalid_calendar_fails_closed(key, override):
    with pytest.raises(ValueError):
        cpm([task('A', 1, calendar_id=key)], [], start=START, calendar=ALL,
            calendars={'week': {**WEEK, **override}})


def test_calendar_exception_and_jalali_leap_crossing_are_explicit():
    from core.projects.jalali_dates import gregorian_to_jalali, jalali_to_gregorian

    day = jalali_to_gregorian('1403/12/30')
    assert day.isoformat() == '2025-03-20'
    calendar = {'weekdays': [0, 1, 2, 3, 4], 'holidays': ['2025-03-21'],
                'working_exceptions': ['2025-03-22']}
    result = cpm([task('A', 2, calendar_id='x'), task('M', 0)], [edge('A', 'M')],
                 start='2025-03-20', calendar=ALL, calendars={'x': calendar})
    assert gregorian_to_jalali(date.fromisoformat(result['activities']['A']['finish'])) == '1404/01/02'
    assert result['activities']['M']['start'] == '2025-03-23'


def test_resource_calendar_change_is_audited_and_visible_in_lookahead(tmp_path):
    from test_phase4_structure import activity, cmd, structure
    from core.platform.application import StructuralProApp

    with_source = tmp_path / 'source.txt'
    with_source.write_text('Synthetic schedule evidence', encoding='utf-8')
    from hashlib import sha256
    proof = {'path': str(with_source), 'sha256': sha256(with_source.read_bytes()).hexdigest(), 'reference': 'TEST'}
    service = StructuralProApp(tmp_path)
    try:
        service.create_project('Synthetic calendars', 'P')
        structure(service)
        activity(service, 'A')
        def site(op, actor='maker', **data):
            return service.site_command('P', op, actor=actor, reason='synthetic',
                expected_version=service.open_project('P')['_meta']['version'], **data)
        site('policy', actor='owner', owner='owner', establish_owner=True, source=proof,
             permissions={k: ['maker', 'reviewer', 'approver', 'owner'] for k in ('create','review','approve','issue','adjust','finance')})
        site('resource_create', id='C', name='Crew', kind='crew', capacity='1', unit='crew',
             discipline_id='S', subcontractor='synthetic', source=proof)
        site('resource_review', actor='reviewer', id='C')
        site('resource_approve', actor='approver', id='C')
        cmd(service, 'schedule_calendar', start=START, calendar=ALL,
            calendars={'crew': WEEK}, resource_calendars={'C': 'crew'})
        cmd(service, 'schedule_activity', id='A', duration=2, resource_ids=['C'], relationships=[])
        site('requirements', id='R', activity_id='A', resources=[{'resource_id':'C','quantity':'1'}], materials=[], source=proof)
        site('availability', id='AV', resource_id='C', start=START, end='2027-03-26',
             state='present', capacity='1', confirmed=True, source=proof)
        site('assign', id='AS', activity_id='A', resource_id='C', start=START, end='2027-03-26',
             allocation='1', source=proof)
        site('assignment_review', actor='reviewer', id='AS')
        site('assignment_approve', actor='approver', id='AS')
        baseline = cmd(service, 'schedule_baseline', reference='B1', approved_by='reviewer')
        before = service.site_lookahead('P', start=START, days=7)['activities'][0]
        assert before['work_dates'] == ['2027-03-22', '2027-03-23']
        assert before['status'] == 'ready'
        old_assignment = service.open_project('P')['resource_assignments'][0]
        change = cmd(service, 'schedule_calendar', start=START, calendar=ALL,
                     calendars={'crew': {**WEEK, 'holidays':['2027-03-23']}}, resource_calendars={'C':'crew'})
        assert change['calendar_version'] == 2
        after = service.site_lookahead('P', start=START, days=7)['activities'][0]
        assert after['work_dates'] == ['2027-03-22', '2027-03-24']
        assert after['status'] == 'insufficient_information'
        saved = service.open_project('P')
        assert saved['schedule_baselines'] == [baseline]
        assert old_assignment['status'] == 'approved'
        assert saved['resource_assignments'][0] == old_assignment
        before_bad = service.store.current_digest('P')
        with pytest.raises(ValueError):
            cmd(service, 'schedule_activity', id='A', duration=2, calendar_id='missing', relationships=[])
        assert service.store.current_digest('P') == before_bad
    finally:
        service.store.close()


@pytest.mark.parametrize('policy,remaining,expected', [
    ('RETAINED_LOGIC', 2, '2027-03-27'),
    ('RETAINED_LOGIC', 1, '2027-03-26'),
])
def test_forecast_resumes_out_of_sequence_without_rewriting_actuals(tmp_path, policy, remaining, expected):
    from test_phase4_structure import activity, cmd, structure
    from core.platform.application import StructuralProApp

    path = tmp_path / 'evidence.txt'
    path.write_text('Synthetic actuals', encoding='utf-8')
    from hashlib import sha256
    source = {'path':str(path),'sha256':sha256(path.read_bytes()).hexdigest(),'reference':'TEST'}
    service = StructuralProApp(tmp_path)
    try:
        service.create_project('Synthetic status', 'P')
        structure(service)
        for key in ('A', 'B', 'M'):
            activity(service, key)
        cmd(service, 'schedule_calendar', start=START, calendar=ALL)
        cmd(service, 'schedule_activity', id='A', duration=3, relationships=[])
        cmd(service, 'schedule_activity', id='B', duration=2, relationships=[edge('A','B')])
        cmd(service, 'schedule_activity', id='M', duration=0, relationships=[edge('B','M')])
        baseline = cmd(service, 'schedule_baseline', reference='B1', approved_by='reviewer')
        before = service.open_project('P')
        status = cmd(service, 'schedule_status', data_date='2027-03-23', policy=policy,
                     unreported='NOT_STARTED', observations=[
            {'id':'A','state':'IN_PROGRESS','actual_start':'2027-03-20','remaining_duration':2,'source':source},
            {'id':'B','state':'IN_PROGRESS','actual_start':'2027-03-22','remaining_duration':remaining,
             'actual_percent':'10.25','source':source},
        ])
        forecast = service.project_schedule_forecast('P')
        assert status['version'] == 1 and status['forecast_finish'] == expected
        assert forecast['finish_boundary'] == expected
        assert forecast['activities']['B']['resume'] == '2027-03-25'
        assert forecast['activities']['B']['actual_start'] == '2027-03-22'
        assert forecast['activities']['B']['actual_percent'] == '10.25'
        assert forecast['activities']['M']['start'] == expected
        assert forecast['out_of_sequence'] == [{'pred':'A','succ':'B','type':'FS','lag':0,
                                                'reported_event':'2027-03-22','required_event':'2027-03-25'}]
        assert service.project_schedule('P')['finish_boundary'] == '2027-03-25'
        after = service.open_project('P')
        assert after['schedule_baselines'] == [baseline]
        assert all(before.get(k) == after.get(k) for k in ('boq','financial_records','statement_periods','progress_reports'))
        service.store.close()
        service = StructuralProApp(tmp_path)
        assert service.open_project('P') == after
        assert service.project_schedule_forecast('P') == forecast
        path.write_text('changed', encoding='utf-8')
        with pytest.raises(ValueError):
            service.project_schedule_forecast('P')
    finally:
        service.store.close()


@pytest.fixture
def recorded(tmp_path):
    from hashlib import sha256
    from test_phase4_structure import activity, cmd, structure
    from core.platform.application import StructuralProApp
    from core.platform.identity import OperatingSystemIdentity

    class Identity:
        subject = 'synthetic-owner'
        def current(self):
            return OperatingSystemIdentity(self.subject, self.subject, 'fixture', 'test', True)
    identity=Identity()
    proof_path=tmp_path/'observation.txt'
    proof_path.write_text('SYNTHETIC OBSERVATION',encoding='utf-8')
    proof={'path':str(proof_path),'sha256':sha256(proof_path.read_bytes()).hexdigest(),'reference':'TEST'}
    service=StructuralProApp(tmp_path/'project',identity_provider=identity)
    try:
        service.create_project('Status test','P')
        structure(service)
        activity(service,'A')
        activity(service,'B')
        cmd(service,'schedule_calendar',start=START,calendar=ALL)
        cmd(service,'schedule_activity',id='A',duration=2,relationships=[])
        cmd(service,'schedule_activity',id='B',duration=1,relationships=[edge('A','B')])
        yield service,identity,proof
    finally:
        service.store.close()


def status_payload(proof, **fields):
    return {'data_date':'2027-03-23','policy':'RETAINED_LOGIC','unreported':'NOT_STARTED',
            'observations':[{'id':'A','state':'IN_PROGRESS','actual_start':'2027-03-20',
                             'remaining_duration':1,'source':proof,**fields}]}


@pytest.mark.parametrize('changes', [
    {'actual_start':'2027-03-23'}, {'actual_start':'2027-03-19'}, {'actual_finish':'2027-03-21'},
    {'remaining_duration':0}, {'actual_percent':'100'}, {'actual_percent':True}, {'actual_quantity':'1'},
    {'remaining_work':'1'}, {'state':'COMPLETED'}, {'source':{'path':'missing'}},
])
def test_invalid_observations_do_not_change_payload_or_revision(recorded, changes):
    from test_phase4_structure import cmd
    service,_,proof=recorded
    before=service.store.current_digest('P')
    revisions=service.store.revisions('P')
    with pytest.raises(ValueError):
        cmd(service,'schedule_status',**status_payload(proof,**changes))
    assert service.store.current_digest('P')==before
    assert service.store.revisions('P')==revisions


def test_status_edits_append_and_raw_tampering_is_refused(recorded):
    from test_phase4_structure import cmd
    service,_,proof=recorded
    first=cmd(service,'schedule_status',**status_payload(proof))
    with pytest.raises(ValueError):
        cmd(service,'schedule_status',**status_payload(proof))
    next_payload=status_payload(proof,actual_start='2027-03-21')
    next_payload['data_date']='2027-03-24'
    with pytest.raises(ValueError):
        cmd(service,'schedule_status',**next_payload)
    corrected=cmd(service,'schedule_status',corrects_version=1,**status_payload(proof,remaining_duration=2))
    assert corrected['version']==2 and corrected['corrects_version']==1
    assert first['forecast_finish']=='2027-03-25' and corrected['forecast_finish']=='2027-03-26'
    assert service.project_schedule_forecast('P',version=1)['status_sha256']==first['sha256']
    before=service.open_project('P')
    altered=service.open_project('P')
    altered['schedule_status_records'][0]['observations'][0]['remaining_duration']=99
    with pytest.raises(ValueError):
        service.store.save('P',altered)
    assert service.open_project('P')==before


def test_baseline_authorization_and_status_cas_or_write_failure(recorded):
    import sqlite3
    from test_phase4_structure import cmd
    service, identity, proof=recorded
    service.store.grant_role('P','synthetic-editor','editor',reference='TEST')
    identity.subject='synthetic-editor'
    with pytest.raises(PermissionError):
        cmd(service,'schedule_baseline',reference='forbidden',approved_by='text-is-not-authentication')
    identity.subject='synthetic-owner'
    baseline=cmd(service,'schedule_baseline',reference='B1',approved_by='reviewer')
    before=service.open_project('P')
    with pytest.raises(RuntimeError):
        service.project_control_command('P','schedule_status',actor='planner',reason='stale',
            expected_version=before['_meta']['version']-1,**status_payload(proof))
    service.store.db.execute("CREATE TEMP TRIGGER reject_revision BEFORE INSERT ON revisions BEGIN SELECT RAISE(ABORT, 'test write interruption'); END")
    with pytest.raises(sqlite3.IntegrityError,match='test write interruption'):
        cmd(service,'schedule_status',**status_payload(proof))
    service.store.db.execute('DROP TRIGGER reject_revision')
    assert service.open_project('P')==before
    assert service.open_project('P')['schedule_baselines']==[baseline]
    assert service.store.verify_audit('P')
    assert not service.open_project('P').get('schedule_status_records')


def test_removing_dependency_by_raw_save_and_corrupt_status_are_blocked(recorded):
    from test_phase4_structure import cmd
    from core.projects.schedule_status import forecast
    service,_,proof=recorded
    cmd(service,'schedule_status',**status_payload(proof))
    before=service.store.current_digest('P')
    altered=service.open_project('P')
    altered['project_schedule_tasks'].pop(0)
    with pytest.raises(ValueError):
        service.store.save('P',altered)
    altered=service.open_project('P')
    altered['schedule_status_records'][0]['forecast_finish']='2027-03-24'
    with pytest.raises(ValueError,match='تمامیت'):
        forecast(altered)
    assert service.store.current_digest('P')==before


@pytest.mark.parametrize('kind,lag,expected_resume', [
    ('FS',0,'2027-03-25'), ('SS',4,'2027-03-24'),
    ('FF',1,'2027-03-25'), ('SF',6,'2027-03-25'),
])
def test_forecast_keeps_four_relationship_endpoints(recorded,kind,lag,expected_resume):
    from test_phase4_structure import cmd
    service,_,proof=recorded
    cmd(service,'schedule_activity',id='B',duration=1,relationships=[edge('A','B',kind,lag)])
    payload=status_payload(proof,remaining_duration=2)
    cmd(service,'schedule_status',**payload)
    result=service.project_schedule_forecast('P')
    assert result['activities']['B']['resume']==expected_resume


def test_calendar_float_and_relationships_match_civil_enumeration():
    from itertools import product
    start = date.fromisoformat(START)
    choices = {key: [start + timedelta(days=n) for n in range(20)
                     if key != 'A' or (start + timedelta(days=n)).weekday() < 5]
               for key in 'ABM'}
    for kind, lag in product(('FS', 'SS', 'FF', 'SF'), (-1, 0, 1)):
        tasks = [task('A', 2, calendar_id='week'), task('B', 2), task('M', 0)]
        links = [edge('A','B',kind,lag), edge('B','M')]
        result = cpm(tasks, links, start=START, calendar=ALL, calendars={'week':WEEK})
        feasible = []
        for i, j, k in product(range(8), range(10), range(12)):
            a, b, m = choices['A'][i], choices['B'][j], choices['M'][k]
            fa, fb = choices['A'][i+1]+timedelta(days=1), b+timedelta(days=2)
            before, after = (fa if kind[0]=='F' else a), (fb if kind[1]=='F' else b)
            if after >= before+timedelta(days=lag) and m >= fb:
                feasible.append((max(fa,fb,m),(i,j,k)))
        end=min(e for e,_ in feasible)
        optimal=[v for e,v in feasible if e==end]
        early=tuple(map(min,zip(*optimal)))
        late=tuple(map(max,zip(*optimal)))
        assert result['finish_boundary']==end.isoformat()
        for i,key in enumerate('ABM'):
            row=result['activities'][key]
            free=max(v[i] for v in optimal if all(v[j]==early[j] for j in range(3) if i!=j))
            assert (row['start'],row['late_start'],row['total_float'],row['free_float'])==(
                choices[key][early[i]].isoformat(),choices[key][late[i]].isoformat(),late[i]-early[i],free-early[i])


def test_shared_equipment_calendar_and_capacity_remain_separate(tmp_path):
    from test_phase4_structure import activity, cmd, structure
    from core.platform.application import StructuralProApp
    from test_phase8_p2_b_golden import resource, site, synthetic_source
    proof=synthetic_source(tmp_path)
    service=StructuralProApp(tmp_path/'p')
    try:
        service.create_project('Shared equipment','P')
        structure(service)
        activity(service,'A')
        activity(service,'B')
        site(service,'policy',actor='owner',owner='owner',establish_owner=True,source=proof,
             permissions={k:['maker','reviewer','approver','owner'] for k in ('create','review','approve','issue','adjust','finance')})
        resource(service,'L','equipment',proof,'1')
        cmd(service,'schedule_calendar',start='2027-03-22',calendar=ALL,calendars={'lift':WEEK},
            resource_calendars={'L':'lift'})
        for key in ('A','B'):
            cmd(service,'schedule_activity',id=key,duration=2,resource_ids=['L'],relationships=[])
        for key in ('A','B'):
            site(service,'assign',id='AS-'+key,activity_id=key,resource_id='L',start='2027-03-22',
                 end='2027-03-23',allocation='1',source=proof)
        site(service,'assignment_review',actor='reviewer',id='AS-A')
        site(service,'assignment_approve',actor='approver',id='AS-A')
        with pytest.raises(ValueError,match='تداخل ظرفیت'):
            site(service,'assignment_review',actor='reviewer',id='AS-B')
        schedule=service.project_schedule('P')
        assert schedule['activities']['A']['start']==schedule['activities']['B']['start']=='2027-03-22'
        assert service.open_project('P')['resource_assignments'][1]['status']=='draft'
    finally:
        service.store.close()


def test_completed_actual_on_last_planned_workday_has_zero_variance(recorded):
    from test_phase4_structure import cmd
    service,_,proof=recorded
    start='2027-03-26'
    cmd(service,'schedule_calendar',start=start,calendar=WEEK)
    cmd(service,'schedule_activity',id='A',duration=1,relationships=[])
    cmd(service,'schedule_activity',id='B',duration=0,relationships=[])
    cmd(service,'schedule_baseline',reference='B1',approved_by='reviewer')
    status=cmd(service,'schedule_status',data_date='2027-03-27',policy='RETAINED_LOGIC',
               unreported='NOT_STARTED',observations=[
        {'id':key,'state':'COMPLETED','actual_start':start,'actual_finish':start,
         'remaining_duration':0,'source':proof} for key in ('A','B')
    ])
    assert status['forecast_finish']=='2027-03-29'
    assert status['baseline_delta_days']==0
    assert service.project_schedule_forecast('P')['activities']['A']['actual_finish']==start


def test_independent_draft_rejects_resource_calendar_before_writing_offsets():
    plan={'tasks':[{'id':'A','duration_days':1,'predecessors':[],'resource_ids':['L']}]}
    with pytest.raises(ValueError):
        calculate_precedence(plan)
    assert 'start_workday_offset' not in plan['tasks'][0]


def test_workday_index_matches_daily_oracle_with_holidays_and_exceptions():
    from core.projects.scheduling import WorkCalendar
    first=date(2027,3,20)
    off={date(2027,3,23),date(2027,4,1)}
    extra={date(2027,3,21),date(2027,4,3)}
    cal=WorkCalendar({'weekdays':[0,1,2,3,4],'holidays':sorted(map(str,off)),
                      'working_exceptions':sorted(map(str,extra))},first.isoformat())
    opened=[]
    for i in range(90):
        day=first+timedelta(days=i)
        assert cal.index_day(day)==len(opened)
        if day in extra or day.weekday()<5 and day not in off:
            assert cal.at(len(opened))==day
            opened.append(day)


def test_cumulative_percent_requires_correction_instead_of_silent_decrease(recorded):
    from test_phase4_structure import cmd
    service,_,proof=recorded
    cmd(service,'schedule_status',**status_payload(proof,actual_percent='70'))
    for fields in ({'actual_percent':'5'},{}):
        payload=status_payload(proof,**fields)
        payload['data_date']='2027-03-24'
        with pytest.raises(ValueError,match='کارکرد تجمعی'):
            cmd(service,'schedule_status',**payload)
    result=cmd(service,'schedule_status',corrects_version=1,**status_payload(proof,actual_percent='5'))
    assert result['version']==2


def test_replanning_project_origin_preserves_prior_actual_dates(recorded):
    from test_phase4_structure import cmd
    service,_,proof=recorded
    first=cmd(service,'schedule_status',**status_payload(proof))
    cmd(service,'schedule_calendar',start='2027-03-21',calendar=ALL)
    payload=status_payload(proof)
    payload['data_date']='2027-03-24'
    second=cmd(service,'schedule_status',**payload)
    assert second['version']==2
    assert second['observations'][0]['actual_start']==first['observations'][0]['actual_start']==START
    assert service.project_schedule_forecast('P')['version']==2


def test_legacy_calendar_edit_preserves_explicit_exceptions(recorded):
    from test_phase4_structure import cmd
    service,_,_=recorded
    cmd(service,'schedule_calendar',start=START,calendar={**WEEK,'working_exceptions':[START]})
    saved=cmd(service,'schedule_calendar',start=START,calendar={**WEEK,'holidays':['2027-03-22']})
    assert saved['calendar']['working_exceptions']==[START]
    assert service.project_schedule('P')['activities']['A']['start']==START


def test_management_cpm_accepts_iterables_and_named_calendars():
    from core.projects.management import ProjectManagement
    result=ProjectManagement.calculate_cpm(iter([task('A',1,calendar_id='week')]),iter([]),
                                          start=START,calendar=ALL,calendars={'week':WEEK})
    assert result['activities']['A']['start']=='2027-03-22'


def test_qt_preserves_saved_project_exceptions_and_labels_forecast_as_proposed(recorded):
    from json import dumps
    from PySide6.QtWidgets import QApplication, QPushButton
    from app.project_controls_workspace import ProjectControlsWorkspace
    from test_phase4_structure import cmd

    service,_,proof=recorded
    cmd(service,'schedule_calendar',start=START,calendar={**WEEK,'working_exceptions':[START]})
    qt=QApplication.instance() or QApplication([])
    view=ProjectControlsWorkspace(service,'P')
    try:
        assert view.fields['project_exceptions'].text()
        view.fields['actor'].setText('planner')
        view.fields['reason'].setText('synthetic Qt test')
        view.findChild(QPushButton,'ScheduleCalendarSave').click()
        assert service.open_project('P')['project_control_config']['schedule']['calendar']['working_exceptions']==[START]
        view.fields['schedule_data_date'].setText('2027-03-23')
        view.status_policy.setChecked(True)
        view.status_observations.setPlainText(dumps(status_payload(proof)['observations']))
        view.findChild(QPushButton,'ScheduleStatusSave').click()
        assert 'پایان پیش‌بینی پیشنهادی' in view.schedule_info.text()
        assert service.project_schedule_forecast('P')['status']=='PROPOSED_UNAPPROVED'
    finally:
        view.close()
        qt.processEvents()
