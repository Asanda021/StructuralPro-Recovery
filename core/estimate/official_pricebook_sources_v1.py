"""Evidence-backed registry for Iranian Abnieh pricebook sources.

The registry records publication/source evidence only. It never embeds rates.
Direct SAMA pages are used where verified; otherwise the official portal is
recorded and the row remains a source-catalog entry until the raw bytes are
retrieved and hashed.
"""
from dataclasses import dataclass
from hashlib import sha256

@dataclass(frozen=True)
class OfficialPricebookSource:
    year: int
    discipline: str
    title: str
    official_url: str
    document_type: str
    circular_date: str
    source_status: str

SOURCES = (
    OfficialPricebookSource(1399,"ابنیه","فهرست بهای واحد پایه رشته ابنیه سال ۱۳۹۹",
        "https://sama.mporg.ir/","official-publication-portal","1398/12/27","official-portal"),
    OfficialPricebookSource(1400,"ابنیه","فهرست بهای واحد پایه رشته ابنیه سال ۱۴۰۰",
        "https://sama.mporg.ir/","official-publication-portal","1399/12/25","official-portal"),
    OfficialPricebookSource(1401,"ابنیه","فهرست بهای واحد پایه رشته ابنیه سال ۱۴۰۱",
        "https://sama.mporg.ir/sites/publish/SitePages/ZabetehView.aspx?mdid=5681","official-publication-page","1400/12/28","official-page"),
    OfficialPricebookSource(1402,"ابنیه","فهرست بهای واحد پایه رشته ابنیه سال ۱۴۰۲",
        "https://sama.mporg.ir/","official-publication-portal","1401/12/28","official-portal"),
    OfficialPricebookSource(1403,"ابنیه","فهرست بهای واحد پایه رشته ابنیه سال ۱۴۰۳",
        "https://sama.mporg.ir/sites/publish/SitePages/ZabetehView.aspx?mdid=5852","official-publication-page","1402/12/26","official-page"),
    OfficialPricebookSource(1404,"ابنیه","فهرست بهای واحد پایه رشته ابنیه سال ۱۴۰۴",
        "https://sama.mporg.ir/sites/publish/SitePages/ZabetehView.aspx?mdid=5957","official-publication-page","1403/12/29","official-page"),
)

def validate_sources():
    if not SOURCES:
        raise ValueError("official sources required")
    seen=set()
    for s in SOURCES:
        if s.discipline!="ابنیه" or not s.official_url.startswith("https://"):
            raise ValueError("invalid official source")
        if s.source_status not in {"official-page","official-portal"}:
            raise ValueError("invalid source status")
        if s.year in seen:
            raise ValueError("duplicate source year")
        seen.add(s.year)
    return True

def registry_fingerprint():
    validate_sources()
    raw="|".join(
        f"{s.year}|{s.discipline}|{s.title}|{s.official_url}|{s.document_type}|{s.circular_date}|{s.source_status}"
        for s in SOURCES
    )
    return sha256(raw.encode()).hexdigest()

RAW_FILE_CANDIDATES = {1404: "https://sama.mporg.ir/DigitalAsset/DigitalAsset/FehrestBaha1404.rar?Web=1"}

def raw_file_candidates():
    return dict(RAW_FILE_CANDIDATES)

def coverage():
    validate_sources()
    years=sorted(s.year for s in SOURCES)
    return {"discipline":"ابنیه","years":years,"min_year":years[0],"max_year":years[-1],"count":len(years)}

BUILDING_1404_DISCIPLINES = ("ابنیه","تاسیسات مکانیکی","تاسیسات برقی","مرمت بناهای تاریخی")

def building_1404_coverage():
    present={s.discipline for s in SOURCES if s.year==1404}
    missing=[d for d in BUILDING_1404_DISCIPLINES if d not in present]
    return {"year":1404,"required":list(BUILDING_1404_DISCIPLINES),"present":sorted(present),"missing":missing,"complete":not missing}

BUILDING_SOURCES_1404 = (
    OfficialPricebookSource(1404,"تاسیسات مکانیکی","فهرست بهای واحد پایه رشته تاسیسات مکانیکی سال ۱۴۰۴","https://sama.mporg.ir/","official-publication-portal","1403/12/29","official-portal"),
    OfficialPricebookSource(1404,"تاسیسات برقی","فهرست بهای واحد پایه رشته تاسیسات برقی سال ۱۴۰۴","https://sama.mporg.ir/","official-publication-portal","1403/12/29","official-portal"),
    OfficialPricebookSource(1404,"مرمت بناهای تاریخی","فهرست بهای واحد پایه رشته مرمت بناهای تاریخی سال ۱۴۰۴","https://sama.mporg.ir/","official-publication-portal","1403/12/29","official-portal"),
)

def all_building_sources():
    return SOURCES + BUILDING_SOURCES_1404
