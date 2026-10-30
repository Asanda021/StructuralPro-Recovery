"""Professional report layout model: columns, grouping, totals, RTL and pagination."""
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from .decimal_values import exact_sum

_FIELD_MAP = {"ردیف": "item_no", "کد": "price_code", "شرح": "description", "مقدار": "quantity", "واحد": "unit", "بهای واحد": "unit_price", "مبلغ": "total", "منبع": "source"}


def _exact_total(value):
    """Preserve the source's decimal digits; never round a reported subtotal via float."""
    if value is None or value == "":
        return Decimal("0")
    if isinstance(value, bool):
        raise ValueError("invalid report total: boolean")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("invalid report total: nonnumeric") from exc
    if not result.is_finite():
        raise ValueError("invalid report total: nonfinite")
    return result


@dataclass
class ReportLayout:
    title: str = "گزارش متره و برآورد"
    columns: list[str] = field(default_factory=lambda: ["ردیف", "کد", "شرح", "مقدار", "واحد", "بهای واحد", "مبلغ"])
    group_by: str = ""
    rtl: bool = True
    page_size: int = 35
    header: str = ""
    footer: str = ""

    def visible(self, row):
        out = {label: row.get(_FIELD_MAP.get(label, label), row.get(label, "")) for label in self.columns}
        for key in ("item_no", "price_code", "description", "quantity", "unit", "unit_price", "total", "source"):
            out.setdefault(key, row.get(key, ""))
        return out

    def reorder(self, columns):
        self.columns = list(columns)
        return self

    def render_rows(self, rows):
        if not self.group_by:
            return [self.visible(row) for row in rows]
        key = self.group_by
        out = []
        sentinel = object()
        current = sentinel
        subtotal_values = []
        for source in rows:
            r = self.visible(source)
            g = source.get(key, r.get(key, ""))
            if current is not sentinel and g != current:
                out.append({key: f"جمع {current}", "مبلغ": exact_sum(subtotal_values)})
            if g != current:
                current, subtotal_values = g, []
            subtotal_values.append(_exact_total(r.get("مبلغ", r.get("total", ""))))
            out.append(r)
        if current is not sentinel:
            out.append({key: f"جمع {current}", "مبلغ": subtotal})
        return out

    def pages(self, rows):
        if self.page_size < 1:
            raise ValueError("page_size must be positive")
        rendered = self.render_rows(rows)
        return [rendered[i:i + self.page_size] for i in range(0, len(rendered), self.page_size)] or [[]]
