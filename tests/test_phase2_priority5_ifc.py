"""Real IFC4 fixtures; analytic oracles are constants, never product output."""
from decimal import Decimal
from pathlib import Path
import hashlib
import pytest
import ifcopenshell as ifc
from core.drawings.bim_adapter import BIMAdapter


def model_file(path, *, millimetres=False, quantity_unit=False):
    m=ifc.file(schema='IFC4');new=ifc.guid.new
    project=m.create_entity('IfcProject',GlobalId=new(),Name='آزمون BIM')
    factor=1000. if millimetres else 1.
    unit=m.create_entity('IfcSIUnit',UnitType='LENGTHUNIT',Name='METRE',Prefix='MILLI' if millimetres else None)
    project.UnitsInContext=m.create_entity('IfcUnitAssignment',Units=[unit])
    def axes(x,y,z,rot=False):
        return m.create_entity('IfcAxis2Placement3D',Location=m.create_entity('IfcCartesianPoint',Coordinates=(x*factor,y*factor,z*factor)),RefDirection=m.create_entity('IfcDirection',DirectionRatios=(0.,1.,0.) if rot else (1.,0.,0.)))
    building=m.create_entity('IfcBuilding',GlobalId=new(),Name='ساختمان',ObjectPlacement=m.create_entity('IfcLocalPlacement',RelativePlacement=axes(1000000.,2.,0.,True)))
    m.create_entity('IfcRelAggregates',GlobalId=new(),RelatingObject=project,RelatedObjects=[building])
    context=m.create_entity('IfcGeometricRepresentationContext',ContextType='Model',CoordinateSpaceDimension=3,Precision=1e-5,WorldCoordinateSystem=axes(0.,0.,0.))
    project.RepresentationContexts=[context]
    members=[]
    for n in range(2):
        st=m.create_entity('IfcBuildingStorey',GlobalId=new(),Name=f'طبقه {n+1}',Elevation=n*3.*factor,ObjectPlacement=m.create_entity('IfcLocalPlacement',PlacementRelTo=building.ObjectPlacement,RelativePlacement=axes(0.,0.,n*3.)))
        m.create_entity('IfcRelAggregates',GlobalId=new(),RelatingObject=building,RelatedObjects=[st])
        for typ in ('IfcBeam','IfcColumn','IfcSlab','IfcWall','IfcFooting','IfcMember'):
            obj=m.create_entity(typ,GlobalId=new(),Name=typ+' فارسی',ObjectPlacement=m.create_entity('IfcLocalPlacement',PlacementRelTo=st.ObjectPlacement,RelativePlacement=axes(5.,0.,0.)))
            m.create_entity('IfcRelContainedInSpatialStructure',GlobalId=new(),RelatedElements=[obj],RelatingStructure=st)
            profile=m.create_entity('IfcRectangleProfileDef',ProfileType='AREA',XDim=4.*factor,YDim=.2*factor)
            solid=m.create_entity('IfcExtrudedAreaSolid',SweptArea=profile,Position=axes(0.,0.,0.),ExtrudedDirection=m.create_entity('IfcDirection',DirectionRatios=(0.,0.,1.)),Depth=3.*factor)
            rep=m.create_entity('IfcShapeRepresentation',ContextOfItems=context,RepresentationIdentifier='Body',RepresentationType='SweptSolid',Items=[solid])
            obj.Representation=m.create_entity('IfcProductDefinitionShape',Representations=[rep])
            qunit=m.create_entity('IfcSIUnit',UnitType='LENGTHUNIT',Name='METRE') if quantity_unit else None
            q=m.create_entity('IfcQuantityLength',Name='Length',LengthValue=4. if quantity_unit else 4.*factor,Unit=qunit)
            qset=m.create_entity('IfcElementQuantity',GlobalId=new(),Name='Qto_Test',MethodOfMeasurement='synthetic explicit dimensions',Quantities=[q])
            m.create_entity('IfcRelDefinesByProperties',GlobalId=new(),RelatedObjects=[obj],RelatingPropertyDefinition=qset)
            members.append(obj)
    m.write(str(path));return m,members


def read(path):return BIMAdapter().read_document(path,revision='R1')


@pytest.mark.parametrize('mm,override',[(False,False),(True,False),(True,True)])
def test_units_nested_placements_and_quantity_oracle(tmp_path,mm,override):
    p=tmp_path/'مدل.ifc';m,objects=model_file(p,millimetres=mm,quantity_unit=override)
    doc=read(p)
    assert doc['schema']=='IFC4' and doc['parser'].startswith('IfcOpenShell ')
    assert doc['source_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    assert len(doc['storeys'])==2 and len(doc['elements'])==12
    assert {r['ifc_type'] for r in doc['elements']}=={'IfcBeam','IfcColumn','IfcSlab','IfcWall','IfcFooting','IfcMember'}
    a=next(e for e in doc['elements'] if e['global_id']==objects[0].GlobalId)
    assert tuple(Decimal(v) for v in a['origin_m'])==(Decimal('1000000'),Decimal('7'),Decimal('0'))
    assert a['storey_id']==doc['storeys'][0]['global_id']
    q=a['quantities'][0]
    assert Decimal(q['value_si'])==Decimal('4') and q['unit']=='m'
    assert q['source_kind']=='explicit_qto' and not a['commit_allowed']
    assert all(e['payable_rows']==[] for e in doc['elements'])


@pytest.mark.parametrize('mutation,reason',[
    ('duplicate','تکراری'),('missing','GlobalId'),('units','واحد'),('negative','کمیت'),
    ('duplicate_qto','تکراری'),('ambiguous_spatial','فضایی'),('cycle','چرخه'),
    ('direction','جهت'),('project','پروژه'),('unit_conflict','واحد')])
def test_invalid_real_ifc_rejected(tmp_path,mutation,reason):
    p=tmp_path/'bad.ifc';m,objects=model_file(p);o=objects[0]
    if mutation=='duplicate':objects[1].GlobalId=o.GlobalId
    elif mutation=='missing':o.GlobalId=None
    elif mutation=='units':m.by_type('IfcProject')[0].UnitsInContext=None
    elif mutation=='negative':m.by_type('IfcQuantityLength')[0].LengthValue=-1.
    elif mutation=='duplicate_qto':
        s=m.by_type('IfcElementQuantity')[0];s.Quantities=list(s.Quantities)+[m.create_entity('IfcQuantityLength',Name='Length',LengthValue=5.)]
    elif mutation=='ambiguous_spatial':m.create_entity('IfcRelContainedInSpatialStructure',GlobalId=ifc.guid.new(),RelatedElements=[o],RelatingStructure=m.by_type('IfcBuildingStorey')[1])
    elif mutation=='cycle':o.ObjectPlacement.PlacementRelTo=o.ObjectPlacement
    elif mutation=='direction':o.ObjectPlacement.RelativePlacement.RefDirection.DirectionRatios=(0.,0.,0.)
    elif mutation=='project':m.create_entity('IfcProject',GlobalId=ifc.guid.new())
    elif mutation=='unit_conflict':
        project=m.by_type('IfcProject')[0];project.UnitsInContext.Units=list(project.UnitsInContext.Units)+[m.create_entity('IfcSIUnit',UnitType='LENGTHUNIT',Name='METRE')]
    m.write(str(p))
    with pytest.raises(ValueError,match=reason):read(p)


def test_qto_area_volume_units_and_gross_net_are_distinct(tmp_path):
    p=tmp_path/'qto.ifc';m,objects=model_file(p,millimetres=True)
    qset=m.by_type('IfcElementQuantity')[0]
    qset.Quantities=[m.create_entity('IfcQuantityArea',Name='GrossArea',AreaValue=20000000.),m.create_entity('IfcQuantityArea',Name='NetArea',AreaValue=18000000.),m.create_entity('IfcQuantityVolume',Name='NetVolume',VolumeValue=2400000000.)]
    m.write(str(p));e=next(x for x in read(p)['elements'] if x['global_id']==objects[0].GlobalId)
    q={v['name']:v for v in e['quantities']}
    assert Decimal(q['GrossArea']['value_si'])==20
    assert Decimal(q['NetArea']['value_si'])==18
    assert Decimal(q['NetVolume']['value_si'])==Decimal('2.4')
    assert q['GrossArea']['basis']=='gross' and q['NetArea']['basis']=='net'


@pytest.mark.parametrize('payload',[b'',b'not IFC',b'{"schema":"IFC4"}',b'ISO-10303-21;'])
def test_invalid_files(tmp_path,payload):
    p=tmp_path/'bad.ifc';p.write_bytes(payload)
    with pytest.raises(ValueError):read(p)


def test_ifc_projected_session_cannot_bypass_ui_financial_lock(tmp_path):
    from core.platform.application import StructuralProApp
    from core.drawings.takeoff_session import DrawingTakeoffSession
    from core.drawings.graphical_takeoff import Point
    p=tmp_path/'source.ifc';model_file(p)
    service=StructuralProApp(tmp_path/'app');service.create_project('IFC guard','P')
    session=DrawingTakeoffSession(str(p));session.calibrate(1,1,1)
    session.add_length([Point(0,0),Point(3,4)],label='unreviewed projected line',takeoff_code='TEST')
    saved=service.save_drawing_takeoff_session('P',session)
    before=service.store.current_digest('P')
    with pytest.raises(ValueError,match='IFC'):
        service.commit_drawing_takeoff_to_boq('P',saved['session_id'],[session.items[0].id],expected_session_revision=saved['revision'])
    assert service.store.current_digest('P')==before
    assert service.open_project('P').get('boq',[])==[]
    service.store.close()


def test_identity_proposal_uses_actual_project_members_sqlite_and_cas(tmp_path):
    from core.platform.application import StructuralProApp
    p=tmp_path/'source.ifc';_,objs=model_file(p)
    service=StructuralProApp(tmp_path/'app');service.create_project('IFC identity','P')
    service.add_project_floor('P','طبقه اول',level='F1')
    service.add_project_member('P','B1','F1','beam')
    digest=service.store.current_digest('P')
    assert hasattr(service,'save_ifc_identity_proposal')
    result=service.save_ifc_identity_proposal('P',str(p),revision='R1',global_id=objs[0].GlobalId,floor_id='F1',member_id='B1',author='author',reference='synthetic explicit mapping; not engineering approval',expected_digest=digest,source_sha256=hashlib.sha256(p.read_bytes()).hexdigest())
    assert result['status']=='proposed' and result['commit_allowed'] is False
    assert result['payable_rows']==[] and result['document']['source_sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    with pytest.raises(RuntimeError):
        service.save_ifc_identity_proposal('P',str(p),revision='R1',global_id=objs[1].GlobalId,floor_id='F1',member_id='B1',author='author',reference='stale',expected_digest=digest,source_sha256=hashlib.sha256(p.read_bytes()).hexdigest())
    before=service.store.current_digest('P')
    with pytest.raises(ValueError):
        service.save_ifc_identity_proposal('P',str(p),revision='R1',global_id=objs[0].GlobalId,floor_id='missing',member_id='B1',author='author',reference='bad floor',expected_digest=before,source_sha256=hashlib.sha256(p.read_bytes()).hexdigest())
    assert service.store.current_digest('P')==before
    service.store.close()
    reopened=StructuralProApp(tmp_path/'app')
    assert reopened.open_project('P')['ifc_identity_proposals'][0]==result
    assert reopened.open_project('P').get('boq',[])==[]
    assert reopened.store.integrity_check()['ok']
    reopened.store.close()


def test_qt_ifc_inspector_real_selection_filter_and_proposal(tmp_path):
    from PySide6.QtWidgets import QApplication,QLineEdit,QPushButton,QTreeWidget,QComboBox,QLabel
    from PySide6.QtTest import QTest
    from PySide6.QtCore import Qt
    from app.graphical_takeoff import GraphicalTakeoffDialog
    from core.platform.application import StructuralProApp
    app=QApplication.instance() or QApplication([])
    p=tmp_path/'model.ifc';_,objects=model_file(p)
    service=StructuralProApp(tmp_path/'app');service.create_project('IFC Qt','P')
    service.add_project_floor('P','طبقه اول',level='F1');service.add_project_member('P','B1','F1','beam')
    w=GraphicalTakeoffDialog(app_service=service,project_id='P');w.show();w.open_drawing(str(p))
    try:
        assert hasattr(w,'ifc_inspect_button')
        QTest.keyClicks(w.ifc_revision,'R1');QTest.mouseClick(w.ifc_inspect_button,Qt.LeftButton);QTest.qWait(20)
        dlg=w._ifc_inspector;tree=dlg.findChild(QTreeWidget,'ifc_tree')
        search=dlg.findChild(QLineEdit,'ifc_search');QTest.keyClicks(search,objects[0].GlobalId)
        leaf=tree.topLevelItem(0).child(0)
        assert leaf.data(0,Qt.UserRole)==objects[0].GlobalId
        QTest.mouseClick(tree.viewport(),Qt.LeftButton,pos=tree.visualItemRect(leaf).center())
        assert w._ifc_selected_global_id==objects[0].GlobalId
        assert any(x.isSelected() for x in w._ifc_handle_items[objects[0].GlobalId])
        assert '4' in dlg.findChild(QLabel,'ifc_detail').text()
        QTest.keyClicks(dlg.findChild(QLineEdit,'ifc_author'),'tester')
        QTest.keyClicks(dlg.findChild(QLineEdit,'ifc_reference'),'explicit synthetic proposal')
        QTest.mouseClick(dlg.findChild(QPushButton,'ifc_save_proposal'),Qt.LeftButton)
        assert service.open_project('P')['ifc_identity_proposals'][0]['member_id']=='B1'
        assert service.open_project('P').get('boq',[])==[]
        assert w.session.items==[]
        w.grab().save(str(tmp_path/'ifc-viewer.png'));dlg.grab().save(str(tmp_path/'ifc-inspector.png'))
        dlg.close()
    finally:w.close();service.store.close()


@pytest.mark.parametrize('kind,kwargs',[
    ('IfcQuantityLength',{'LengthValue':4.}),
    ('IfcQuantityArea',{'AreaValue':20.}),
    ('IfcQuantityVolume',{'VolumeValue':2.4}),
    ('IfcQuantityCount',{'CountValue':6.})])
def test_explicit_qto_unit_dimension_and_provenance(tmp_path,kind,kwargs):
    p=tmp_path/'units.ifc';m,objs=model_file(p)
    qset=m.by_type('IfcElementQuantity')[0];qset.Quantities=[m.create_entity(kind,Name='DocumentedValue',**kwargs)]
    m.write(str(p));e=next(x for x in read(p)['elements'] if x['global_id']==objs[0].GlobalId)
    q=e['quantities'][0];assert Decimal(q['value_si'])==Decimal(str(next(iter(kwargs.values()))))
    assert q['qset_id']==qset.GlobalId and q['step_id']>0 and q['source_kind']=='explicit_qto'
    assert q['basis']=='unspecified' and e['commit_allowed'] is False


def test_missing_qto_never_becomes_mesh_material_quantity(tmp_path):
    p=tmp_path/'noqto.ifc';m,objs=model_file(p)
    qset=m.by_type('IfcElementQuantity')[0];qset.Quantities=[];m.write(str(p))
    e=next(x for x in read(p)['elements'] if x['global_id']==objs[0].GlobalId)
    assert e['quantities']==[] and e['payable_rows']==[]


@pytest.mark.parametrize('kind,value', [('IfcQuantityCount',1.5),('IfcQuantityLength',1e-25)])
def test_fractional_count_and_unreliable_tiny_quantity_rejected(tmp_path,kind,value):
    p=tmp_path/'tiny.ifc';m,_=model_file(p)
    attr='CountValue' if kind=='IfcQuantityCount' else 'LengthValue'
    m.by_type('IfcElementQuantity')[0].Quantities=[m.create_entity(kind,Name='Bad',**{attr:value})];m.write(str(p))
    with pytest.raises(ValueError):read(p)


def test_unsupported_schema_and_map_conversion_not_claimed(tmp_path):
    p=tmp_path/'ifc2x3.ifc';m=ifc.file(schema='IFC2X3');m.write(str(p))
    with pytest.raises(ValueError,match='Schema'):read(p)
    p=tmp_path/'ifc4.ifc';model_file(p);doc=read(p)
    assert doc['map_conversion_supported'] is False


def test_existing_unified_ifc_inspection_uses_si_qto_and_not_price_inference(tmp_path):
    from core.drawings.unified_takeoff import UnifiedDrawingTakeoff
    p=tmp_path/'millimetres.ifc';model_file(p,millimetres=True)
    result=UnifiedDrawingTakeoff().inspect(p)
    assert result['kind']=='bim'
    assert len(result['candidates'])==12
    assert all(Decimal(str(q['quantity']))==4 and q['unit']=='m' for q in result['candidates'])
    assert all(q.get('commit_allowed') is False and q.get('source_sha256')==hashlib.sha256(p.read_bytes()).hexdigest() for q in result['candidates'])


def test_ifc_preview_cannot_be_promoted_by_generic_confirmation(tmp_path):
    from core.drawings.unified_takeoff import UnifiedDrawingTakeoff
    from core.takeoff.workflow import TakeoffWorkflow
    p=tmp_path/'preview.ifc';model_file(p)
    result=UnifiedDrawingTakeoff().inspect(p)
    with pytest.raises(ValueError,match='IFC'):UnifiedDrawingTakeoff().candidates_to_rows(result,{1:True})
    with pytest.raises(ValueError,match='IFC'):TakeoffWorkflow().confirm(result,{1})


def test_async_ifc_load_cancel_replace_and_responsive_event_loop(tmp_path):
    import time
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer
    from PySide6.QtTest import QTest
    from app.graphical_takeoff import GraphicalTakeoffDialog
    app=QApplication.instance() or QApplication([])
    p=tmp_path/'async.ifc';m,objs=model_file(p);base=objs[0];st=m.by_type('IfcBuildingStorey')[0]
    for i in range(988):
        obj=m.create_entity('IfcBeam',GlobalId=ifc.guid.new(),Name='Stress',ObjectPlacement=base.ObjectPlacement,Representation=base.Representation)
        m.create_entity('IfcRelContainedInSpatialStructure',GlobalId=ifc.guid.new(),RelatedElements=[obj],RelatingStructure=st)
    m.write(str(p));w=GraphicalTakeoffDialog();w.show();ticks=[time.monotonic()];timer=QTimer();timer.timeout.connect(lambda:ticks.append(time.monotonic()));timer.start(10)
    try:
        w.open_cad_async(str(p));assert w.cad_loading and not w.commit_boq_button.isEnabled()
        end=time.monotonic()+60
        while w.cad_loading and time.monotonic()<end:QTest.qWait(10)
        QTest.qWait(50);ticks.append(time.monotonic())
        assert not w.cad_loading and w.viewer.kind=='ifc'
        assert len(w.viewer.ifc_document.meshes)==1000 and len(w._ifc_handle_items)==1000
        assert max(b-a for a,b in zip(ticks,ticks[1:]))<.5
        assert not w.finish.isEnabled() and w.ifc_controls.isVisible()
        previous=w.viewer.ifc_document
        w.open_cad_async(str(p));w.cancel_cad_loading();assert w.viewer.ifc_document is previous
        bad=tmp_path/'bad.ifc';bad.write_text('broken');w.open_cad_async(str(bad))
        end=time.monotonic()+10
        while w.cad_loading and time.monotonic()<end:QTest.qWait(10)
        assert w.viewer.ifc_document is previous and w.session.items==[]
    finally:timer.stop();w.close()


def test_qto_decimal_source_digits_survive_ifcopenshell_double_boundary(tmp_path):
    import re
    p=tmp_path/'precision.ifc';m,objs=model_file(p)
    q=m.by_type('IfcQuantityLength')[0]
    raw=p.read_text();value='3.500000000000000014'
    raw,n=re.subn(r'(#'+str(q.id())+r'=IFCQUANTITYLENGTH\([^,]*,[^,]*,[^,]*,)4\.',r'\g<1>'+value,raw,count=1)
    assert n==1;p.write_text(raw)
    e=next(x for x in read(p)['elements'] if x['global_id']==objs[0].GlobalId)
    assert Decimal(e['quantities'][0]['value_si'])==Decimal(value)
