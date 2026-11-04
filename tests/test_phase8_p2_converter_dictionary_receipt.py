"""Synthetic end-to-end offline converter receipt for nonfinancial DXF diagnostics."""
from pathlib import Path
from types import SimpleNamespace

import ezdxf
from core.drawings.dwg_converter import OfflineDWGConverter


def test_cli_success_keeps_three_dangling_refs_visible_and_financial_veto(tmp_path, monkeypatch):
    src=tmp_path/'synthetic.dwg'
    src.write_bytes(b'AC1018' + b'SYNTHETIC_FILE_NOT_A_REAL_DWG')
    target=tmp_path/'out'

    def fake_converter(command, **kwargs):
        assert command[1]=='-o'
        doc=ezdxf.new('R2018')
        doc.modelspace().add_line((0,0),(1,1))
        map_dict=doc.rootdict.add_new_dict('Autodesk_MAP')
        aec_dict=doc.rootdict.add_new_dict('AEC_VARS')
        map_dict['MAP_DISPLAY_MANAGEMENT_DICTIONARY']='77524'
        map_dict['MAP_DISPLAY_STYLELIBRARY_DICTIONARY']='77525'
        aec_dict['AEC_VARS_DWG_SETUP']='7752D'
        doc.saveas(command[2])
        return SimpleNamespace(returncode=0, stdout='SUCCESS', stderr='')

    monkeypatch.setattr(OfflineDWGConverter,'_run',lambda self,cmd,**kw: fake_converter(cmd,**kw))
    receipt=OfflineDWGConverter('dwg2dxf').convert(src,target)
    # Successful exit is not a native dwg_read_file() bitmask sample.
    cli = receipt.source_coverage['libredwg_c_api_diagnostic']
    assert cli['cli_exit_code'] == 0
    assert cli['c_api_error_mask'] is None
    assert cli['c_api_error_mask_verified'] is False
    assert cli['c_api_status'] == 'NOT_OBSERVED_C_API_BITMASK_CLI_ONLY'
    assert cli['financial_quantity_approved'] is False
    inspection=receipt.source_coverage['converted_dxf_named_dictionary_integrity']
    assert inspection['dangling_or_invalid_count']==3
    assert inspection['converted_dxf_namespace_integrity_status']=='BROKEN_DXF_DICTIONARY_LINKS'
    assert inspection['financial_quantity_approved'] is False
    assert receipt.output.exists()  # read-only source preview remains possible


def test_cli_success_with_no_custom_dict_never_certifies_source_graph(tmp_path,monkeypatch):
    src=tmp_path/'synthetic.dwg'
    src.write_bytes(b'AC1018' + b'SYNTHETIC_FILE_NOT_A_REAL_DWG')
    def fake_converter(command,**kwargs):
        doc=ezdxf.new('R2018');doc.modelspace().add_line((0,0),(1,1));doc.saveas(command[2])
        return SimpleNamespace(returncode=0,stdout='SUCCESS',stderr='')
    monkeypatch.setattr(OfflineDWGConverter,'_run',lambda self,cmd,**kw:fake_converter(cmd,**kw))
    receipt=OfflineDWGConverter('dwg2dxf').convert(src,tmp_path/'out')
    integrity=receipt.source_coverage['converted_dxf_named_dictionary_integrity']
    assert integrity['source_coverage_verified'] is False
    assert integrity['dangling_or_invalid_count']==0
    assert integrity['namespaces']=={'Autodesk_MAP':'NOT_PRESENT_IN_DXF','AEC_VARS':'NOT_PRESENT_IN_DXF'}