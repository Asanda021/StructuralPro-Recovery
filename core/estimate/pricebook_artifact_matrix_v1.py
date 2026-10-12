"""P100 — explicit 1399–1404 building pricebook artifact matrix."""
YEARS=tuple(range(1399,1405))
DISCIPLINES=("ابنیه","تاسیسات مکانیکی","تاسیسات برقی","مرمت بناهای تاریخی")

def empty_matrix():
    return {(y,d):None for y in YEARS for d in DISCIPLINES}

def validate_matrix(matrix):
    expected={(y,d) for y in YEARS for d in DISCIPLINES}
    actual=set(matrix)
    if actual!=expected: raise ValueError("pricebook matrix keys are incomplete")
    missing=[k for k,v in matrix.items() if not v]
    return {"complete":not missing,"missing":tuple(missing),"cells":len(matrix)}

def record(matrix,year,discipline,artifact):
    key=(int(year),str(discipline))
    if key not in matrix: raise ValueError("unsupported pricebook matrix cell")
    if not artifact or not artifact.get("sha256"): raise ValueError("artifact provenance required")
    matrix[key]=dict(artifact)
    return matrix
