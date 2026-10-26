"""Reproducible IFC4 *synthetic fixture* scaling: 1/5/20/50/100 floors.

This is not a claim about an actual building. IFC coordinates/placements and
triangulated geometry are independently constructed and all members must load.
"""
from __future__ import annotations

import gc
import json
import os
import platform
import threading
import time
from pathlib import Path

import pytest


def make_ifc_floors(path, count):
    import ifcopenshell as ifc
    assert count in {1,5,20,50,100}
    model=ifc.file(schema='IFC4')
    new=ifc.guid.new
    p=model.create_entity('IfcProject',GlobalId=new(),Name='SYNTHETIC SCALING FIXTURE')
    unit=model.create_entity('IfcSIUnit',UnitType='LENGTHUNIT',Name='METRE')
    p.UnitsInContext=model.create_entity('IfcUnitAssignment',Units=[unit])
    def axes(x=0.,y=0.,z=0.):
        return model.create_entity('IfcAxis2Placement3D',
            Location=model.create_entity('IfcCartesianPoint',
                                         Coordinates=(float(x),float(y),float(z))))
    b=model.create_entity('IfcBuilding',GlobalId=new(),Name='TEST BUILDING',
                          ObjectPlacement=model.create_entity('IfcLocalPlacement',
                                                             RelativePlacement=axes()))
    model.create_entity('IfcRelAggregates',GlobalId=new(),RelatingObject=p,RelatedObjects=[b])
    ctx=model.create_entity('IfcGeometricRepresentationContext',
                             ContextType='Model',CoordinateSpaceDimension=3,
                             Precision=1e-5,WorldCoordinateSystem=axes())
    p.RepresentationContexts=[ctx]
    expected=set()
    for floor in range(count):
        storey=model.create_entity('IfcBuildingStorey',GlobalId=new(),
                                   Name='SYNTHETIC FLOOR '+str(floor),
                                   Elevation=float(floor)*3.,
                                   ObjectPlacement=model.create_entity(
                                        'IfcLocalPlacement',PlacementRelTo=b.ObjectPlacement,
                                        RelativePlacement=axes(0,0,floor*3)))
        model.create_entity('IfcRelAggregates',GlobalId=new(),
                            RelatingObject=b,RelatedObjects=[storey])
        for offset,typ in enumerate(('IfcBeam','IfcWall','IfcSlab','IfcDuctSegment')):
            prod=model.create_entity(typ,GlobalId=new(),Name='TEST '+typ,
                ObjectPlacement=model.create_entity(
                    'IfcLocalPlacement',PlacementRelTo=storey.ObjectPlacement,
                    RelativePlacement=axes(offset*5,0,0)))
            model.create_entity('IfcRelContainedInSpatialStructure',GlobalId=new(),
                                RelatingStructure=storey,RelatedElements=[prod])
            profile=model.create_entity('IfcRectangleProfileDef',ProfileType='AREA',
                                        XDim=2.0,YDim=0.35)
            geom=model.create_entity('IfcExtrudedAreaSolid',SweptArea=profile,
               Position=axes(),ExtrudedDirection=model.create_entity(
                   'IfcDirection',DirectionRatios=(0.,0.,1.)),Depth=2.5)
            shape=model.create_entity('IfcShapeRepresentation',ContextOfItems=ctx,
               RepresentationIdentifier='Body',RepresentationType='SweptSolid',Items=[geom])
            prod.Representation=model.create_entity('IfcProductDefinitionShape',Representations=[shape])
            expected.add(prod.GlobalId)
    model.write(str(path))
    return expected


@pytest.mark.parametrize('floors',[1,5,20,50,100])
def test_ifc_real_parse_100_floor_scaling_is_measured_without_dropping_members(tmp_path, floors):
    from core.bim.ifc import DeepIFCAdapter
    from core.drawings.source_mesh3d import VerifiedScene3D
    import psutil
    source=tmp_path/('synthetic-%d.ifc'%floors)
    expected=make_ifc_floors(source,floors)
    process=psutil.Process()
    gc.collect()
    rss_before=process.memory_info().rss
    peak=[rss_before]
    running=threading.Event();running.set()
    def memory_sample():
        while running.is_set():
            try:peak[0]=max(peak[0],process.memory_info().rss)
            except psutil.Error:pass
            time.sleep(.02)
    sampler=threading.Thread(target=memory_sample,daemon=True);sampler.start()
    start=time.perf_counter()
    try:
        contract=DeepIFCAdapter().read_display_contract(source,revision='BENCH-R1',
                                                        max_triangles=40_000)
        scene=VerifiedScene3D(contract)
        t_loaded=time.perf_counter()
        visible=scene.visible_faces(1000,740)
        t_faces=time.perf_counter()
        scene.orbit(.3,.15);scene.set_zoom(1.2)
        after=scene.visible_faces(1000,740)
        t_camera=time.perf_counter()
        selected=scene.visible_faces(1000,740,storey_id=scene.storeys[0])
        t_floor=time.perf_counter()
    finally:
        running.clear();sampler.join(timeout=2)
    peak[0]=max(peak[0],process.memory_info().rss)
    members={m.global_id for m in scene.meshes}
    assert members==expected
    assert len(scene.storeys)==floors
    assert scene.omitted_ids==()
    assert len(visible)==len(after)==len(expected)*12
    assert len(selected)==4*12
    metrics={
        'scenario':'synthetic IFC4 fixtures, not a real construction project',
        'floor_count':floors,
        'member_count':len(scene.meshes),
        'triangle_count':len(visible),
        'omitted_count':len(scene.omitted_ids),
        'seconds_parse_and_scene':round(t_loaded-start,4),
        'seconds_first_frame':round(t_faces-t_loaded,4),
        'seconds_orbit_zoom':round(t_camera-t_faces,4),
        'seconds_floor_filter':round(t_floor-t_camera,4),
        'seconds_total':round(t_floor-start,4),
        'rss_before_bytes':rss_before,
        'rss_peak_sampled_bytes':peak[0],
        'rss_growth_peak_bytes':peak[0]-rss_before,
        'python':platform.python_version(),
        'os':platform.platform(),
        'machine':platform.machine(),
        'cpu_count':os.cpu_count(),
        'thresholds':{
            'total_seconds_lt':180,
            'peak_rss_growth_bytes_lt':1_500_000_000,
            'first_frame_seconds_lt':10,
            'orbit_zoom_seconds_lt':10,
            'floor_filter_seconds_lt':10,
        },
    }
    directory=Path(os.getenv('STRUCTURALPRO_P6_P2_BENCH_DIR',str(tmp_path)))
    directory.mkdir(parents=True,exist_ok=True)
    (directory/('ifc4-%03d-floors.json'%floors)).write_text(
        json.dumps(metrics,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PHASE6_P2_BENCHMARK '+json.dumps(metrics,ensure_ascii=False),flush=True)
    assert metrics['seconds_total'] < 180
    assert metrics['rss_growth_peak_bytes'] < 1_500_000_000
    assert metrics['seconds_first_frame'] < 10
    assert metrics['seconds_orbit_zoom'] < 10
    assert metrics['seconds_floor_filter'] < 10
