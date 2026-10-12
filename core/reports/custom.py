"""User-defined report projections without changing source rows."""

def build_custom_report(rows, columns, order=None):
    rows=list(rows)
    cols=list(order or columns)
    return [{c:r.get(c, "") for c in cols} for r in rows]
