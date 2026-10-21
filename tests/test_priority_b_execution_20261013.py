"""Independent fail-closed P10–12 edge cases; real catalog and BOQ paths."""
import pytest
from core.pricing.catalog import PriceCatalog, PriceItem
from core.pricing.import_service import PricebookImportService
from core.takeoff.boq import build_boq
from core.takeoff.commit_guards import rebuild_project_boq


def _csv(tmp_path, rows):
    path = tmp_path / 'prices.csv'
    path.write_text('year,group,chapter,code,description,unit,unit_price\n' + '\n'.join(rows) + '\n', encoding='utf-8')
    return path


@pytest.mark.parametrize('rows', [
    ['1404.9,building,01,A,Concrete,m3,100'],
    ['1405,building,01,A,Concrete,m3,100'],
    ['1404,building,01,A,Concrete,m3,100', '1404,building,01,A,Concrete,m3,200'],
])
def test_price_import_invalid_year_or_duplicate_preserves_catalog(tmp_path, rows):
    catalog = PriceCatalog([PriceItem(1404, 'building', '01', 'OLD', 'Old', 'm3', 50)])
    service = PricebookImportService(catalog)
    before = catalog.export_csv()
    with pytest.raises(ValueError):
        service.import_file(_csv(tmp_path, rows), year=1404)
    assert catalog.export_csv() == before


def test_zero_excel_price_is_explicit_and_valid(tmp_path):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(['year', 'code', 'description', 'unit', 'unit_price'])
    ws.append([1404, 'ZERO', 'Zero price', 'm3', 0])
    path = tmp_path / 'prices.xlsx'
    wb.save(path)
    catalog = PriceCatalog()
    PricebookImportService(catalog).import_file(path, year=1404)
    assert catalog.get('ZERO', 1404).unit_price == 0


def test_boq_aggregation_rejects_quantity_overflow():
    rows = [dict(source_id=source, description='Concrete', unit='m3', quantity=1e308)
            for source in ('A', 'B')]
    with pytest.raises(ValueError):
        build_boq(rows)


def test_rebuild_rejects_unmeasured_stored_takeoff():
    with pytest.raises(ValueError):
        rebuild_project_boq({}, [{'source_id': 'lost', 'quantities': []}])


def test_boq_independent_reference_retains_allowance_cost_and_all_sources():
    rows = [dict(source_id='A', description='Steel', unit='kg', quantity=10,
                 waste_percent=10, allowance_quantity=2, unit_price=50, factor=1.2),
            dict(source_id='B', description='Steel', unit='kg', quantity=20,
                 waste_percent=10, allowance_quantity=3, unit_price=50, factor=1.2)]
    result = build_boq(rows)[0]
    # Hand calculation: (10+1+2 + 20+2+3) kg * 50 * 1.2 = 2280.
    assert result['quantity'] == 30
    assert result['effective_quantity'] == 38
    assert result['total'] == 2280
    assert result['source_ids'] == ['A', 'B']


@pytest.mark.parametrize('explicit', [True, False])
def test_finish_boq_bills_work_once_and_keeps_procurement_audit(explicit):
    rows = []
    for role, amount in [('work', 28), ('procurement', 30.8), ('material', 560)]:
        quantity = dict(code='wall_tile_' + role, title=role, unit='m2', amount=amount, unit_price=100)
        if explicit:
            quantity['role'] = role
        rows.append(dict(source_id=role, params={'assembly_code': 'wall_tile'}, quantities=[quantity]))
    takeoffs, boq = rebuild_project_boq({}, rows)
    assert len(takeoffs) == 3
    assert len(boq) == 1
    assert boq[0]['total'] == 2800  # 28 m2 * 100; purchase figures are audit only.


def test_unknown_component_role_never_becomes_payable():
    row = dict(source_id='bad', quantities=[dict(code='x', title='x', unit='m2', amount=1, role='guess')])
    with pytest.raises(ValueError):
        rebuild_project_boq({}, [row])


@pytest.mark.parametrize('module_name,function_name', [
    ('scripts.run_core_acceptance_offline', 'run'),
    ('scripts.run_group2_acceptance_offline', 'verify'),
])
def test_acceptance_counts_only_terminal_summary(tmp_path, monkeypatch, module_name, function_name):
    import importlib
    import json
    import subprocess
    module = importlib.import_module(module_name)
    def completed(command, **kwargs):
        if command[0] == 'git':
            return subprocess.CompletedProcess(command, 0, 'test-commit\n', '')
        return subprocess.CompletedProcess(command, 0, 'captured text: 999 passed, 12 skipped\n1 passed in 0.01s\n', '')
    monkeypatch.setattr(module.subprocess, 'run', completed)
    report = tmp_path / 'report.json'
    assert getattr(module, function_name)(report) == 0
    data = json.loads(report.read_text())
    assert data['counts']['passed'] == 1
    assert data['counts']['skipped'] == 0


def test_legacy_nested_block_wall_bills_net_area_once():
    quantities = [dict(code=code, title=code, unit=unit, amount=amount, unit_price=100)
                  for code, unit, amount in [('wall_area', 'm2', 28), ('block', 'count', 350),
                                             ('mortar', 'm3', .8), ('cement', 'm3', .2), ('sand', 'm3', .6)]]
    row = dict(source_id='wall', params={'assembly_code': 'block_wall'}, quantities=quantities)
    takeoffs, boq = rebuild_project_boq({}, [row])
    assert len(takeoffs[0]['quantities']) == 5
    assert len(boq) == 1
    assert boq[0]['item_code'] == 'wall_area'
    assert boq[0]['total'] == 2800  # net28m²*100; 5 material figures remain auditable.


def test_generic_concrete_formwork_and_rebar_remain_payable():
    row = dict(source_id='column', quantities=[
        dict(code='concrete', title='Concrete', unit='m3', amount=.6),
        dict(code='formwork', title='Formwork', unit='m2', amount=5.4),
        dict(code='rebar', title='Rebar', unit='kg', amount=48)])
    _, boq = rebuild_project_boq({}, [row])
    assert {x['item_code'] for x in boq} == {'concrete', 'formwork', 'rebar'}


def test_price_receipt_and_items_use_identical_file_bytes(tmp_path, monkeypatch):
    from hashlib import sha256
    path = _csv(tmp_path, ['1404,building,01,A,Concrete,m3,100'])
    original = path.read_bytes()
    service = PricebookImportService(PriceCatalog())
    loader = service._load_items
    def replace_before_parse(file_path, **kwargs):
        path.write_text('year,group,chapter,code,description,unit,unit_price\n1404,building,01,B,Replaced,m3,900\n', encoding='utf-8')
        return loader(file_path, **kwargs)
    monkeypatch.setattr(service, '_load_items', replace_before_parse)
    receipt = service.import_file(path, year=1404)
    assert receipt.sha256 == sha256(original).hexdigest()
    assert service.catalog.get('A', 1404).unit_price == 100
    assert service.catalog.get('B', 1404) is None


@pytest.mark.parametrize('module_name,function_name', [
    ('scripts.run_core_acceptance_offline', 'run'),
    ('scripts.run_group2_acceptance_offline', 'verify'),
])
def test_acceptance_rejects_deselected_cases(tmp_path, monkeypatch, module_name, function_name):
    import importlib
    import subprocess
    module = importlib.import_module(module_name)
    def completed(command, **kwargs):
        output = 'test-commit\n' if command[0] == 'git' else '1 passed, 2 deselected in 0.01s\n'
        return subprocess.CompletedProcess(command, 0, output, '')
    monkeypatch.setattr(module.subprocess, 'run', completed)
    assert getattr(module, function_name)(tmp_path / 'report.json') != 0
