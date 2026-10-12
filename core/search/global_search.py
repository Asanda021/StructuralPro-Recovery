"""Fast in-memory global project search."""
def search_project(project,query):
    q=str(query or "").casefold().strip()
    if not q:return []
    hits=[]
    def hit(kind,text,data):
        if q in str(text).casefold(): hits.append({"kind":kind,"text":str(text),"data":data})
    hit("project",project.get("name",""),project)
    for t in project.get("takeoffs",[]):
        hit("takeoff",t.get("title",""),t)
        for x in t.get("quantities",[]):
            hit("item",x.get("title",""),x); hit("price_code",x.get("price_code",""),x)
    for x in project.get("boq",[]): hit("boq",x.get("description",""),x); hit("price_code",x.get("price_code",""),x)
    return hits
