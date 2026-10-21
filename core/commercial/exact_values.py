"""Exact numeric boundaries and lossless JSON compatibility, not another engine."""
from decimal import Decimal,localcontext,Inexact,Rounded,DecimalException
from functools import wraps
from core.commercial.statement_amendment import number

def wire(value):
    if isinstance(value,Decimal):
        if value==value.to_integral_value():
            return int(value) if abs(value)<10**15 else format(value,"f")
        candidate=float(value)
        if Decimal(str(candidate))==value:return candidate
        return format(value,'f')
    if isinstance(value,dict):return {k:wire(v) for k,v in value.items()}
    if isinstance(value,list):return [wire(v) for v in value]
    return value

def exact(fn):
    @wraps(fn)
    def run(*args,**kwargs):
        with localcontext() as ctx:
            ctx.prec=512;ctx.traps[Inexact]=True;ctx.traps[Rounded]=True
            try:return fn(*args,**kwargs)
            except DecimalException as e:raise ValueError('دقت محاسبه مالی قابل حفظ نیست؛ محاسبه متوقف شد') from e
    return run

def display_percent(a,b):
    # Non-payable presentation ratio, never used as a monetary multiplier.
    with localcontext() as ctx:
        ctx.traps[Inexact]=False;ctx.traps[Rounded]=False
        return float(a/b*100) if b else 0.0
