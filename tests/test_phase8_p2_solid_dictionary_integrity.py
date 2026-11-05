"""Synthetic regression only: no private drawings or source approval."""
from types import SimpleNamespace

import ezdxf
import pytest
from core.drawings.dwg_source_display_integrity import (
    source_solid_3d_preview_manifest,
    converted_dxf_solid_3d_diagnostic,
    audit_named_dictionary_links,
)


def solid(points, elevation=0, extrusion=(0, 0, 1)):
    attrs = {'elevation': elevation, 'extrusion': extrusion}
    attrs.update({'vtx'+str(i): p for i,p in enumerate(points)})
    return SimpleNamespace(dxftype=lambda: 'SOLID', dxf=SimpleNamespace(get=lambda k,default=None: attrs.get(k, default)))


def test_native_xyz_receipt_has_no_financial_authority():
    info=source_solid_3d_preview_manifest([(0,0,-5),(1,0,-5),(1,1,-5),(1,1,-5)])
    assert info['native_source_vertices_3d'][0][2]==-5
    assert info['cad_3d_gui_render_verified'] is False
    assert info['financial_quantity_approved'] is False


@pytest.mark.parametrize('bad', [[],[(1,2,3)]*5,[(0,0,float('nan'))]*4,[(1,2,1e25)]*4])
def test_native_invalid_vertices_blocked(bad):
    with pytest.raises(ValueError):source_solid_3d_preview_manifest(bad)


def test_native_nonstandard_extrusion_blocked():
    with pytest.raises(ValueError,match='Nonstandard'):
        source_solid_3d_preview_manifest([(0,0,1)]*3, (0,1,0))


def test_dxf_legacy_group38_is_diagnostic_only():
    data=converted_dxf_solid_3d_diagnostic(solid([(0,0,0),(1,0,0),(1,1,0),(1,1,0)],-5.25))
    assert data['status']=='GROUP38_ELEVATION_RECONSTRUCTED_DIAGNOSTIC_ONLY'
    assert all(v[2]==-5.25 for v in data['diagnostic_wcs_vertices_3d'])
    assert data['cad_3d_gui_render_verified'] is False
    assert data['financial_quantity_approved'] is False


def test_dxf_direct_z_is_retained():
    d=converted_dxf_solid_3d_diagnostic(solid([(0,0,1),(1,0,1),(1,1,1),(1,1,1)]))
    assert d['status']=='WCS_VERTEX_Z_PRESENT_DIAGNOSTIC_ONLY'
    assert d['diagnostic_wcs_vertices_3d'][0][2]==1


def test_dxf_conflicting_z_is_not_silently_added():
    d=converted_dxf_solid_3d_diagnostic(solid([(0,0,1)]*4,5))
    assert d['status']=='MIXED_VERTEX_Z_AND_ELEVATION_AMBIGUOUS'
    assert d['diagnostic_wcs_vertices_3d'] is None


def test_dxf_nonstandard_extrusion_is_unverified():
    d=converted_dxf_solid_3d_diagnostic(solid([(0,0,0)]*4,3,(1,0,0)))
    assert d['status']=='NONSTANDARD_EXTRUSION_3D_UNVERIFIED'
    assert d['financial_quantity_approved'] is False


@pytest.mark.parametrize('z', [float('nan'), float('inf'), 1e25])
def test_dxf_invalid_elevation_throws(z):
    with pytest.raises(ValueError):converted_dxf_solid_3d_diagnostic(solid([(0,0,0)]*4,z))


def test_dxf_wrong_type_throws():
    with pytest.raises(ValueError,match='Expected'):
        converted_dxf_solid_3d_diagnostic(SimpleNamespace(dxftype=lambda:'LINE'))


def test_dxf_empty_dictionary_namespaces_not_approval():
    d=ezdxf.new('R2018')
    r=audit_named_dictionary_links(d)
    assert r['dangling_or_invalid_count']==0
    assert r['source_coverage_verified'] is False


def test_two_custom_dictionaries_three_real_dangling_handles():
    d=ezdxf.new('R2018')
    m=d.rootdict.add_new_dict('Autodesk_MAP'); a=d.rootdict.add_new_dict('AEC_VARS')
    m['FIRST']='77524';m['SECOND']='77525';a['SETUP']='7752D'
    r=audit_named_dictionary_links(d)
    assert r['dangling_or_invalid_count']==3
    assert {i['target_handle'] for i in r['dangling_or_invalid_references']}=={'77524','77525','7752D'}
    assert r['converted_dxf_namespace_integrity_status']=='BROKEN_DXF_DICTIONARY_LINKS'


def test_existing_dictionary_target_not_reported_broken():
    d=ezdxf.new('R2018')
    c=d.rootdict.add_new_dict('AEC_VARS');obj=d.objects.add_xrecord();c['SETUP']=obj
    r=audit_named_dictionary_links(d)
    assert r['dangling_or_invalid_count']==0
    assert r['original_dwg_custom_payloads_verified'] is False


def test_bad_namespace_root_fail_closed():
    d=ezdxf.new('R2018');d.rootdict['Autodesk_MAP']='ABCDEF'
    r=audit_named_dictionary_links(d)
    assert r['dangling_or_invalid_count']==1
    assert r['dangling_or_invalid_references'][0]['reason']=='ROOT_TARGET_UNRESOLVED'


def test_imported_named_dictionary_not_doc_rootdict_still_detected():
    # A converted DXF can carry imported NOD 1A while ezdxf synthesizes a
    # different doc.rootdict; checking only the convenience root misses links.
    d = ezdxf.new('R2018')
    old_root = d.objects.add_dictionary()
    namespace = d.objects.add_dictionary()
    old_root['Autodesk_MAP'] = namespace
    namespace['BROKEN'] = '77524'
    assert d.rootdict.dxf.handle != old_root.dxf.handle
    got = audit_named_dictionary_links(d)
    assert got['root_dictionary_handle'] == old_root.dxf.handle
    assert got['dangling_or_invalid_count'] == 1


def test_ambiguous_named_dictionary_roots_cannot_claim_clean():
    d = ezdxf.new('R2018')
    d.rootdict.add_new_dict('AEC_VARS')
    legacy = d.objects.add_dictionary()
    legacy['Autodesk_MAP'] = d.objects.add_dictionary()
    got = audit_named_dictionary_links(d)
    assert got['converted_dxf_namespace_integrity_status'] == 'AMBIGUOUS_NAMED_DICTIONARY_ROOTS'
    assert got['dangling_or_invalid_count'] is None
    assert got['source_coverage_verified'] is False

def test_present_but_empty_map_aec_dictionaries_are_source_unverified():
    # ACadSharp-style structural output: both namespace containers survive,
    # but every original custom instance may have been dropped.
    d = ezdxf.new('R2018')
    d.rootdict.add_new_dict('Autodesk_MAP')
    d.rootdict.add_new_dict('AEC_VARS')
    r = audit_named_dictionary_links(d)
    assert r['dangling_or_invalid_count'] == 0
    assert r['empty_namespace_count'] == 2
    assert set(r['empty_namespaces']) == {'Autodesk_MAP', 'AEC_VARS'}
    assert r['converted_dxf_namespace_integrity_status'] == 'EMPTY_NAMED_NAMESPACE_SOURCE_UNVERIFIED'
    assert r['source_coverage_verified'] is False
    assert r['financial_quantity_approved'] is False
    assert r['automatic_patch_authorized'] is False


def test_one_empty_present_namespace_rejects_false_clean_status():
    d = ezdxf.new('R2018')
    m = d.rootdict.add_new_dict('Autodesk_MAP')
    a = d.rootdict.add_new_dict('AEC_VARS')
    a['SYNTHETIC_REFERENCE'] = d.objects.add_xrecord()
    r = audit_named_dictionary_links(d)
    assert r['dangling_or_invalid_count'] == 0
    assert r['empty_namespace_count'] == 1
    assert r['empty_namespaces'] == ('Autodesk_MAP',)
    assert r['converted_dxf_namespace_integrity_status'] == 'EMPTY_NAMED_NAMESPACE_SOURCE_UNVERIFIED'
    assert r['original_dwg_custom_payloads_verified'] is False


def test_populated_standard_namespaces_are_not_declared_original_source_verified():
    d = ezdxf.new('R2018')
    m = d.rootdict.add_new_dict('Autodesk_MAP')
    a = d.rootdict.add_new_dict('AEC_VARS')
    m['SYNTHETIC_REFERENCE'] = d.objects.add_xrecord()
    a['SYNTHETIC_REFERENCE'] = d.objects.add_xrecord()
    r = audit_named_dictionary_links(d)
    assert r['empty_namespace_count'] == 0
    assert r['converted_dxf_namespace_integrity_status'] == 'NO_DANGLING_LINKS_OBSERVED_IN_TARGETED_NAMESPACES'
    assert r['original_dwg_custom_payloads_verified'] is False
    assert r['financial_quantity_approved'] is False
