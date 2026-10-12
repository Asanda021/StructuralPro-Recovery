from __future__ import annotations
import hashlib,json,re,sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs,urljoin,urlparse
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from core.estimate.pricebook_row_extraction_v2 import extract_xlsx

ARCHIVE_INDEX="https://fehrestbaha.github.io/"
OFFICIAL_INDEX="https://acco.ir/فهرست-بها"
YEARS=range(1399,1405)
DISCIPLINES=("ابنیه","تاسیسات مکانیکی","تاسیسات برقی","مرمت بناهای تاریخی")
DISCIPLINE_SLUGS={"ابنیه":"abnieh","تاسیسات مکانیکی":"mechanic","تاسیسات برقی":"barghi","مرمت بناهای تاریخی":"maremat"}

def norm_text(v):
    return re.sub(r"\s+"," ",v.replace("ي","ی").replace("ك","ک").replace("\u200c"," ")).strip()

class AnchorParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self.href=None; self.text=[]
    def handle_starttag(self,t,a):
        if t=="a": self.href=dict(a).get("href"); self.text=[]
    def handle_data(self,d):
        if self.href is not None: self.text.append(d)
    def handle_endtag(self,t):
        if t=="a" and self.href is not None:
            self.links.append((norm_text(" ".join(self.text)),self.href)); self.href=None; self.text=[]

class ArchiveRowParser(HTMLParser):
    """Capture each archive table row together with its link targets."""
    def __init__(self):
        super().__init__()
        self.rows=[]
        self.in_row=False
        self.row_text=[]
        self.row_links=[]
        self.href=None
        self.anchor_text=[]

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.in_row=True
            self.row_text=[]
            self.row_links=[]
        elif tag == "a" and self.in_row:
            self.href=dict(attrs).get("href")
            self.anchor_text=[]

    def handle_data(self, data):
        if not self.in_row:
            return
        self.row_text.append(data)
        if self.href is not None:
            self.anchor_text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.in_row and self.href is not None:
            self.row_links.append((norm_text(" ".join(self.anchor_text)), self.href))
            self.href=None
            self.anchor_text=[]
        elif tag == "tr" and self.in_row:
            self.rows.append((norm_text(" ".join(self.row_text)), list(self.row_links)))
            self.in_row=False


def archive_index_rows():
    parser=ArchiveRowParser()
    body,_=get(ARCHIVE_INDEX)
    parser.feed(body.decode("utf-8","ignore"))
    return parser.rows


def get(url):
    req=Request(url,headers={"User-Agent":"StructuralPro-PricebookSync/8.0","Accept":"*/*"})
    with urlopen(req,timeout=120) as r: return r.read(),r.headers.get("Content-Type","")

def page_links(page):
    p=AnchorParser(); body,_=get(page); p.feed(body.decode("utf-8","ignore")); return p.links

def archive_page_candidates(y,d):
    slug=DISCIPLINE_SLUGS[d]
    # The archive uses title-cased filenames (e.g. Abnieh_1404.html), not the
    # lowercase names used by the old importer. Keep a deterministic fallback.
    title={"ابنیه":"Abnieh","تاسیسات مکانیکی":"TasisatMekaniki","تاسیسات برقی":"TasisatBarghi","مرمت بناهای تاریخی":"Marmat"}.get(d,slug)
    return [f"{ARCHIVE_INDEX}fehrest_baha_years/{title}_{y}.html",
            f"{ARCHIVE_INDEX}fehrest_baha_years/{slug}_{y}.html"]

def download_links(page,d,y):
    out=[]
    for txt,href in page_links(page):
        if not href: continue
        low=norm_text(f"{txt} {href}").lower()
        path=urlparse(href).path.lower()
        direct_ext=path.endswith((".xlsx",".xls"))
        download_host=any(h in href.lower() for h in ("drive.google.com","drive.usercontent.google.com","1drv.ms","onedrive.live.com"))
        labeled_download=any(k in low for k in ("excel","xlsx","xls","اکسل","download","دانلود"))
        # Do not accept unrelated year/discipline links accidentally present on a page.
        context=norm_text(f"{txt} {href}")
        if direct_ext or download_host or labeled_download:
            out.append(urljoin(page,href))
    return list(dict.fromkeys(out))

def discover_archive_page(y,d):
    errors=[]
    for page in archive_page_candidates(y,d):
        try:
            candidates=download_links(page,d,y)
            if candidates: return page,candidates
        except Exception as exc:
            errors.append(f"{page}: {exc}")
    # The public index puts the year/discipline in the table row, while the
    # anchor text itself is often only "صفحه دانلود". Match row context rather
    # than anchor text so valid archive pages are not missed.
    try:
        seen=set()
        for label,links in archive_index_rows():
            if str(y) not in label or d not in label:
                continue
            for txt,href in links:
                if not href:
                    continue
                page=urljoin(ARCHIVE_INDEX,href)
                if page in seen:
                    continue
                seen.add(page)
                if urlparse(page).path.lower().endswith((".xlsx",".xls")):
                    return page,[page]
                try:
                    candidates=download_links(page,d,y)
                    if candidates:
                        return page,candidates
                except Exception as exc:
                    errors.append(f"{page}: {exc}")
    except Exception as exc:
        errors.append(f"index discovery: {exc}")
    raise RuntimeError("pricebook archive page not found; " + " | ".join(errors))

def google_drive_variants(url):
    u=urlparse(url); q=parse_qs(u.query); file_id=(q.get("id") or [None])[0]
    if not file_id: return [url]
    return list(dict.fromkeys([url,f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t",f"https://drive.google.com/uc?export=download&id={file_id}&confirm=t"]))

def download(url,dst):
    last=None
    for candidate in google_drive_variants(url):
        try:
            data,ctype=get(candidate); head=data[:4096].lower()
            if len(data)<1024 or b"<html" in head or b"<!doctype" in head or b"<title" in head: raise RuntimeError("non-file response")
            dst.parent.mkdir(parents=True,exist_ok=True); dst.write_bytes(data)
            return hashlib.sha256(data).hexdigest(),len(data),ctype,candidate
        except Exception as exc: last=exc
    raise RuntimeError(f"download failed: {last}")

def main():
    raw=ROOT/"data/pricebooks/raw"; norm=ROOT/"data/pricebooks/normalized"
    (ROOT/"data/pricebooks").mkdir(parents=True,exist_ok=True)
    manifest={"index":ARCHIVE_INDEX,"official_index":OFFICIAL_INDEX,"cells":[]}; failures=[]
    for y in YEARS:
        for d in DISCIPLINES:
            try:
                page,candidates=discover_archive_page(y,d)
                parsed=None; file_slug=DISCIPLINE_SLUGS[d]
                for url in candidates:
                    try:
                        dst=raw/str(y)/(file_slug+".xlsx"); digest,size,ctype,used_url=download(url,dst)
                        extracted=extract_xlsx(dst,y,d)
                        if extracted: parsed=(used_url,digest,size,dst,extracted); break
                    except Exception: continue
                if parsed is None: raise RuntimeError(f"no parseable XLSX among {len(candidates)} candidates")
                url,digest,size,dst,extracted=parsed; out=norm/str(y)/(file_slug+".jsonl"); out.parent.mkdir(parents=True,exist_ok=True)
                with out.open("w",encoding="utf-8") as f:
                    for x in extracted:
                        f.write(json.dumps({"year":x.year,"discipline":x.discipline,"item_code":x.item_code,"description":x.description,"unit":x.unit,"unit_price":x.unit_price,"source_sha256":x.source_sha256,"source_file":x.source_file,"source_sheet":x.source_sheet},ensure_ascii=False)+"\n")
                manifest["cells"].append({"year":y,"discipline":d,"source_tier":"archive","archive_page":page,"download_url":url,"local_file":str(dst.relative_to(ROOT)),"normalized_file":str(out.relative_to(ROOT)),"sha256":digest,"bytes":size,"rows":len(extracted),"priced_rows":sum(x.unit_price is not None for x in extracted)})
                print(f"OK {y} {d}: {len(extracted)} rows")
            except Exception as e:
                failures.append({"year":y,"discipline":d,"error":str(e)}); print(f"FAIL {y} {d}: {e}",file=sys.stderr)
    (ROOT/"data/pricebooks/manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    if failures:
        (ROOT/"data/pricebooks/failures.json").write_text(json.dumps(failures,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        raise SystemExit(f"{len(failures)}/24 pricebook cells failed")
    print("ALL 24 PRICEBOOK CELLS EXTRACTED")

if __name__=="__main__": main()
