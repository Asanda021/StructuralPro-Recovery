"""Typed Qt table comparisons without lossy float conversion."""
from decimal import Decimal,InvalidOperation
from datetime import datetime,timezone
import re,unicodedata,weakref
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidgetItem

def natural(value):
    text=unicodedata.normalize('NFKC',str(value)).translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩','01234567890123456789')).casefold()
    return tuple((1,int(p)) if p.isdecimal() else (0,p) for p in re.split(r'(\d+)',text))

def key(value,kind):
    if kind=='number':
        try:
            raw=str(value).translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩','01234567890123456789')).replace('٫','.')
            n=Decimal(raw)
            if n.is_finite():return (0,n)
        except (InvalidOperation,ValueError):pass
        return (1,natural(value))
    if kind=='date':
        try:
            d=datetime.fromisoformat(str(value).replace('Z','+00:00'))
            if d.tzinfo is None:raise ValueError('timezone required')
            u=d.astimezone(timezone.utc);return (0,(u.toordinal(),u.hour,u.minute,u.second,u.microsecond))
        except (ValueError,TypeError):return (1,natural(value))
    return (0,natural(value))

class TypedItem(QTableWidgetItem):
    def __init__(self,item,table,kind,rank):
        super().__init__(item.text());self.setFlags(item.flags())
        for role in (Qt.DecorationRole,Qt.ToolTipRole,Qt.StatusTipRole,Qt.FontRole,Qt.TextAlignmentRole,Qt.BackgroundRole,Qt.ForegroundRole,Qt.CheckStateRole,Qt.SizeHintRole,Qt.UserRole,Qt.UserRole+1):
            value=item.data(role)
            if value is not None:self.setData(role,value)
        self._table=weakref.ref(table);self.kind=kind;self.rank=rank
    def __lt__(self,other):
        a=key(self.data(Qt.UserRole+1) or self.text(),self.kind);b=key(other.data(Qt.UserRole+1) or other.text(),self.kind)
        if a!=b:return a<b
        table=self._table();descending=table is not None and table.horizontalHeader().sortIndicatorOrder()==Qt.DescendingOrder
        return self.rank>getattr(other,'rank',0) if descending else self.rank<getattr(other,'rank',0)
