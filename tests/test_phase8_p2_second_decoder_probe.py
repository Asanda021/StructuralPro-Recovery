"""Synthetic-only tests. They do NOT constitute real proprietary DWG decoding."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pytest

from core.drawings.dwg_second_decoder_probe import probe_original_dwg, save_probe_report


@pytest.fixture
def source(tmp_path):
    p=tmp_path/'synthetic.dwg'
    p.write_bytes(b'AC1018 fake DWG fixture AEC_VARS_DWG_SETUP')
    return p


class FakeEntity:
    def __init__(self, handle, dxftype):
        self.handle, self.dxftype=handle, dxftype


class FakeNative:
    def __init__(self, original_version='AC1018', members=None):
        self.version=original_version
        self.units='unitless'
        self.members=members if members is not None else [FakeEntity(1,'LINE'),FakeEntity(2,'TEXT')]
    def modelspace(self):
        return SimpleNamespace(iter_entities=lambda:iter(self.members))


def load_native(fake):
    return patch('core.drawings.dwg_second_decoder_probe.metadata.version', return_value='0.17.0'),\
           patch('core.drawings.dwg_second_decoder_probe.import_module',return_value=SimpleNamespace(read=lambda _:fake))


def test_real_file_header_sha_is_checked_without_decoder(source):
    with patch('core.drawings.dwg_second_decoder_probe.metadata.version',side_effect=__import__('importlib').metadata.PackageNotFoundError):
        r=probe_original_dwg(source)
    assert r['source_sha256']==hashlib.sha256(source.read_bytes()).hexdigest()
    assert r['source_dwg_signature']=='AC1018'
    assert r['native_raw_ascii_anchors']['AEC_VARS_DWG_SETUP']['occurrences']==1
    assert r['status']=='BLOCKED_NO_INDEPENDENT_DECODER'
    assert r['independent_decoder_executed'] is False
    assert r['geometry_approved_for_financial_takeoff'] is False


def test_wrong_package_version_cannot_run(source):
    with patch('core.drawings.dwg_second_decoder_probe.metadata.version',return_value='0.19.0'):
        r=probe_original_dwg(source)
    assert r['reason']=='DECODER_VERSION_NOT_PINNED'


def test_synthetic_native_modelspace_success_is_still_no_go(source):
    a,b=load_native(FakeNative())
    with a,b:
        r=probe_original_dwg(source)
    assert r['native_modelspace_entity_count']==2
    assert r['native_modelspace_by_type']=={'LINE':1,'TEXT':1}
    assert r['independent_decoder_executed'] is True
    assert r['status']=='PARTIAL_NO_GO'
    assert r['approved_quantities']==0
    assert r['full_source_object_graph_verified'] is False
    assert r['opaque_class_payloads_verified'] is False


@pytest.mark.parametrize('native,reason',[(FakeNative('AC1015'),'NATIVE_READER_VERSION_MISMATCH'),
        (FakeNative(members=[FakeEntity(1,'LINE'),FakeEntity(1,'TEXT')]),'DUPLICATE_OR_INVALID_SOURCE_ENTITY'),
        (FakeNative(members=[FakeEntity('ZZ','LINE')]),'INDEPENDENT_DECODER_FAILED')])
def test_bad_native_roster_fails_closed(source,native,reason):
    a,b=load_native(native)
    with a,b:
        r=probe_original_dwg(source)
    assert r['reason']==reason
    assert r['independent_decoder_executed'] is False
    assert r['geometry_approved_for_financial_takeoff'] is False


def test_source_mutation_during_native_read_rejected(source):
    def read(_):
        source.write_bytes(source.read_bytes()+b'1')
        return FakeNative()
    with patch('core.drawings.dwg_second_decoder_probe.metadata.version',return_value='0.17.0'), \
         patch('core.drawings.dwg_second_decoder_probe.import_module',return_value=SimpleNamespace(read=read)):
        r=probe_original_dwg(source)
    assert r['reason']=='SOURCE_CHANGED_DURING_READ'
    assert r['independent_decoder_executed'] is False


def test_wrong_or_missing_original_source_rejected(tmp_path,source):
    assert probe_original_dwg(tmp_path/'no.dwg')['reason']=='ORIGINAL_DWG_NOT_FOUND'
    source.write_bytes(b'AC1009 not supported')
    assert probe_original_dwg(source)['reason']=='DWG_HEADER_UNSUPPORTED'


def test_json_diagnostic_does_not_modify_source(source,tmp_path):
    h=hashlib.sha256(source.read_bytes()).hexdigest()
    out=tmp_path/'report.json'
    with patch('core.drawings.dwg_second_decoder_probe.metadata.version',return_value='0.19.0'):
        r=save_probe_report(source,out)
    assert json.loads(out.read_text(encoding='utf-8'))==r
    assert hashlib.sha256(source.read_bytes()).hexdigest()==h