"""P8/P2-A PDF registration: no implicit floor repetition or financial approval."""
from copy import deepcopy
import pytest
from core.drawings.pdf_sheet_scope_registration import (
    classify_sheet_title, register_column_grid_against_axes,
)


def sheet(kind, page, doc='PDF001'):
    return {'document_id':doc, 'page':page,'sheet_kind':kind,
            'status':'EXPLICIT_SHEET_TITLE'}


def grid(page,doc='PDF001',xx=None,yy=None):
    return {'document_id':doc,'page':page,
            'status':'VECTOR_GRID_LOCATION_CANDIDATES',
            'axes_x_pt':xx or [180.0,253.4,358.3,451.9,531.4],
            'levels_y_pt':yy or [155.56,297.16,438.76]}


def test_persian_presentation_forms_and_explicit_plan_titles():
    assert classify_sheet_title('ﭘـــﻼن آﮐــﺲ ﺑﻨـــﺪي')['sheet_kind']=='axis_plan'
    assert classify_sheet_title('ﭘـــﻼن ﺗﯿــــﭗ ﺑﻨـــﺪي ﺳــــﺘﻮن ﻫﺎ')['sheet_kind']=='column_type_plan'
    assert classify_sheet_title('ﭘـــﻼن ﭘﯿﻠـــــﻮت')['sheet_kind']=='pilot_floor_plan'
    assert classify_sheet_title('ﭘـــﻼن ﻃﺒﻘــــﻪ ﻫﻤﮑـﻒ')['sheet_kind']=='ground_floor_plan'
    assert classify_sheet_title('ﭘـــﻼن ﻃﺒﻘــــﻪ اول')['sheet_kind']=='first_floor_plan'
    assert classify_sheet_title('ﭘـــﻼن آﺑﺮوﺑـــــﺎم')['sheet_kind']=='roof_drainage_plan'


def test_other_title_is_not_guessed_as_floor():
    assert classify_sheet_title('ﭘـــﻼن ﻓﻨﺪاﺳـــــــﯿﻮن')['sheet_kind']=='foundation_plan'
    assert classify_sheet_title('ﭘـــﻼن ﻗﺎﻟـــﺐ ﺑﻨـــﺪي')['sheet_kind']=='formwork_plan'
    assert classify_sheet_title('ﭘـــﻼن ﺗــــــﯿﺮرﯾﺰي')['sheet_kind']=='beam_layout_plan'
    assert classify_sheet_title('random drawing')['status']=='UNKNOWN_TITLE'


def test_titles_never_prove_placement_on_floors():
    for text in ('پلان طبقه اول','پلان پیلوت','پلان آکس بندی','Column Type Plan'):
        r=classify_sheet_title(text)
        assert r['floor_instance_repetition_verified'] is False
        assert r['floor_instance_multiplier'] is None
        assert r['financially_payable'] is False


def test_provisional_registration_correlates_5x3_but_no_instances():
    result=register_column_grid_against_axes([grid(13),grid(14)],
                                               [sheet('axis_plan',13),sheet('column_type_plan',14)])
    assert result['registered_grid_positions']==15
    reg=result['column_plan_registrations'][0]
    assert reg['axis_plan']=={'document_id':'PDF001','page':13}
    assert reg['max_residual_pt']==0
    assert reg['status']=='PROPOSED_INDEPENDENT_GRID_REGISTRATION'
    assert not reg['approved'] and not reg['financially_payable']
    assert result['accepted_physical_member_count'] is None
    assert result['complete'] is False


def test_small_page_translation_is_supported_not_perceived_as_scale():
    xx=[x+2.5 for x in grid(13)['axes_x_pt']]
    yy=[y-1.3 for y in grid(13)['levels_y_pt']]
    r=register_column_grid_against_axes([grid(13),grid(14,xx=xx,yy=yy)],
                [sheet('axis_plan',13),sheet('column_type_plan',14)])
    reg=r['column_plan_registrations'][0]
    assert reg['status']=='PROPOSED_INDEPENDENT_GRID_REGISTRATION'
    assert reg['translation_pt']==(2.5,-1.3)
    assert reg['max_residual_pt']==0


def test_mismatch_grid_spacing_never_joins_even_if_one_point_aligns():
    xx=[180.0,245.0,359.0,451.9,531.4]
    r=register_column_grid_against_axes([grid(13),grid(14,xx=xx)],
        [sheet('axis_plan',13),sheet('column_type_plan',14)])
    assert r['registered_grid_positions']==0
    assert r['column_plan_registrations'][0]['status']=='BLOCKED_MISSING_MATCHED_AXIS_PLAN'


def test_extra_dimension_line_not_accepted_as_matching_three_levels():
    r=register_column_grid_against_axes([grid(13),grid(14,yy=[155,205,297,439])],
        [sheet('axis_plan',13),sheet('column_type_plan',14)])
    assert r['registered_grid_positions']==0


def test_different_file_without_revision_authority_is_not_matched():
    r=register_column_grid_against_axes([grid(13,'PDF001'),grid(14,'PDF002')],
        [sheet('axis_plan',13,'PDF001'),sheet('column_type_plan',14,'PDF002')])
    assert r['registered_grid_positions']==0


def test_multiple_indistinguishable_axes_plans_are_blocked_not_multiplied():
    r=register_column_grid_against_axes([grid(12),grid(13),grid(14)],
        [sheet('axis_plan',12),sheet('axis_plan',13),sheet('column_type_plan',14)])
    assert r['column_plan_registrations'][0]['status']=='BLOCKED_MULTIPLE_AXES_PLANS'
    assert r['registered_grid_positions']==0


def test_floors_do_not_create_columns_without_column_type_title():
    r=register_column_grid_against_axes([grid(1),grid(2),grid(3)],
        [sheet('pilot_floor_plan',1),sheet('ground_floor_plan',2),sheet('first_floor_plan',3)])
    assert r['column_plan_registrations']==[] and r['registered_grid_positions']==0
    assert not r['financially_payable']


def test_ambiguous_titles_are_excluded():
    r=register_column_grid_against_axes([grid(13),grid(14)],
        [sheet('axis_plan',13),{**sheet('column_type_plan',14),'status':'BLOCKED_MULTIPLE_TITLE_CLASSES'}])
    assert r['registered_grid_positions']==0


def test_invalid_or_nonmonotonic_axis_candidates_blocked():
    for xx in ([180,180,358,452,531],[180,253,300,315,531],[180,float('nan'),358,451,531]):
        r=register_column_grid_against_axes([grid(13),grid(14,xx=xx)],
           [sheet('axis_plan',13),sheet('column_type_plan',14)])
        assert r['registered_grid_positions']==0


def test_mirrored_order_does_not_fake_identity():
    r=register_column_grid_against_axes([grid(13),grid(14,xx=[531,452,358,253,180])],
        [sheet('axis_plan',13),sheet('column_type_plan',14)])
    assert r['registered_grid_positions']==0


def test_tolerance_is_bounded():
    with pytest.raises(ValueError):
        register_column_grid_against_axes([grid(13),grid(14)],
            [sheet('axis_plan',13),sheet('column_type_plan',14)],tolerance_pt=100)


def test_real_pdf_page_title_and_grid_registration_without_financial_claim():
    import pymupdf
    from core.drawings.pdf_grid_instances import detect_vector_grid_positions
    from pathlib import Path
    source=Path('/mnt/data/structuralpro_private/input/naghshe.pdf')
    if not source.is_file():
        pytest.skip('Private PDF fixture not available; protected CI uses synthetic examples')
    with pymupdf.open(source) as d:
        g=[];titles=[]
        for p in (13,14):
            page=d[p-1]
            grid_scan=detect_vector_grid_positions(page,document_id='PDF001',page_number=p)
            g.append({'document_id':'PDF001','page':p,
                      'status':grid_scan['status'],
                      'axes_x_pt':grid_scan['axes_x_pt'],
                      'levels_y_pt':grid_scan['levels_y_pt']})
            titles.append({'document_id':'PDF001','page':p,**classify_sheet_title(page.get_text())})
    r=register_column_grid_against_axes(g,titles)
    assert r['registered_grid_positions']==15
    assert r['column_plan_registrations'][0]['max_residual_pt']==0
    assert r['accepted_physical_member_count'] is None