from core.iran.parity import IranianCoefficient, IranianTakeoffParity, PriceBookVersion, build_project_takeoff, export_project_csv
from core.pricing.catalog import PriceCatalog, PriceItem

def catalog():
    return PriceCatalog([PriceItem(1404,'ابنیه','فصل 1','010101','بتن آماده','m3',1000),PriceItem(1404,'ابنیه','فصل 2','020101','میلگرد','kg',2000),PriceItem(1403,'ابنیه','فصل 1','010101','بتن آماده','m3',800)])

def test_price_book_versions_and_navigation():
    s=IranianTakeoffParity(catalog()); s.register_price_book(PriceBookVersion(1404,'ابنیه','فهرست بهای ابنیه','official','src-1404',True))
    assert s.price_books(year=1404)[0]['version']=='official'; assert s.groups(1404)==['ابنیه']; assert s.chapters(1404,'ابنیه')==['فصل 1','فصل 2']; assert s.items(1404,discipline='ابنیه',chapter='فصل 1')[0]['code']=='010101'

def test_coefficients_are_explicit_and_composable():
    s=IranianTakeoffParity(); s.register_coefficient(IranianCoefficient('OVERHEAD','ضریب بالاسری',1.10)); s.register_coefficient(IranianCoefficient('ADJUST','ضریب تعدیل',1.05)); r=s.apply_coefficients(100,['OVERHEAD','ADJUST']); assert r['quantity']==115.5

def test_price_book_csv_import_export_and_snapshot():
    s=IranianTakeoffParity(); csv_text='year,group,chapter,code,description,unit,unit_price,analysis,notes\n1404,ابنیه,فصل 1,010101,بتن آماده,m3,1000,,\n'; assert s.import_price_book_csv(csv_text)==1; assert '010101' in s.export_price_book_csv(1404); assert s.snapshot(1404,['010101'])['items'][0]['code']=='010101'

def test_project_takeoff_payload_is_portable():
    p=build_project_takeoff(project_id='P-1',project_name='پروژه نمونه',rows=[{'item_code':'010101','description':'بتن آماده','unit':'m3','quantity':12}],price_year=1404,coefficients=['OVERHEAD']); assert p['schema']=='structuralpro.iran.takeoff.v1'; assert p['rows'][0]['price_year']==1404; assert '010101' in export_project_csv([{'project_id':'P-1','project_name':'پروژه نمونه',**p['rows'][0]}])

def test_member_catalog_is_available():
    names={x['member_type'] for x in IranianTakeoffParity().member_catalog()}; assert 'پی منفرد' in names; assert 'تیر' in names; assert 'دال بتنی' in names
