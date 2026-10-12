from core.bim.model import BIMElement
from core.bim.takeoff import quantities
from core.bim.ifc_intelligence_v2 import extract_quantities, compare_bim_to_drawing
from core.bim.ifc_interoperability_v1 import InterchangeRecord, canonical_record, record_fingerprint, round_trip_verify
from core.bim.roundtrip import roundtrip_manifest, verify_manifest

def run_p120():
    elements = (
        BIMElement("3J$BEAM001","IFCBEAM","B-01","structural","beam","Level 1",material_names=("Concrete C30",),properties={"Mark":"B-01"},geometry={"volume":2.5,"length":5.0},source_id="ifc:model.ifc:3J$BEAM001"),
        BIMElement("3J$COL001","IFCCOLUMN","C-01","structural","column","Level 1",material_names=("Concrete C30",),geometry={"volume":1.2},source_id="ifc:model.ifc:3J$COL001"),
        BIMElement("3J$WALL001","IFCWALL","W-01","architectural","wall","Level 1",geometry={"area":18.0},source_id="ifc:model.ifc:3J$WALL001"),
    )
    takeoff = quantities(elements)
    normalized = extract_quantities(elements)
    discrepancies = compare_bim_to_drawing({"3J$BEAM001":2.5,"3J$COL001":1.2},{"3J$BEAM001":2.5,"3J$COL001":1.2})
    source = InterchangeRecord("P120","R1","ifc:model.ifc","structural","IFC4","3J$BEAM001","IfcBeam",(("Mark","B-01"),),(("volume",2.5),))
    returned = InterchangeRecord("P120","R1","ifc:model.ifc","structural","IFC4","3J$BEAM001","IfcBeam",(("Mark","B-01"),),(("volume",2.5),))
    round_trip_ok = round_trip_verify(source, returned)
    fingerprint = record_fingerprint(source)
    manifest = roundtrip_manifest({"elements":[e.__dict__ for e in elements]})
    manifest_ok = verify_manifest(manifest)
    volume = sum(q.quantity for q in takeoff if q.unit=="m3")
    statuses = [x.status for x in discrepancies]
    verified = len(takeoff)==3 and len(normalized)>=3 and volume==3.7 and statuses==["match","match"] and round_trip_ok and bool(canonical_record(source)) and len(fingerprint)==64 and manifest_ok
    return {"verified":verified,"element_count":len(elements),"takeoff_count":len(takeoff),"normalized_quantity_count":len(normalized),"explicit_volume_m3":volume,"drawing_statuses":statuses,"round_trip":round_trip_ok,"fingerprint":fingerprint,"manifest_verified":manifest_ok}
