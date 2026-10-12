"""Safe formula engine for user-defined takeoff formulas."""
from __future__ import annotations
import ast, math, operator

_OP={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,
     ast.Div:operator.truediv,ast.Pow:operator.pow,ast.USub:operator.neg}

def evaluate(expression,variables):
    try:
        tree=ast.parse(str(expression),mode="eval")
    except (SyntaxError,ValueError) as exc:
        raise ValueError("فرمول نامعتبر است") from exc

    def ev(n):
        if isinstance(n,ast.Expression): return ev(n.body)
        if isinstance(n,ast.Constant) and isinstance(n.value,(int,float)) and not isinstance(n.value,bool):
            return float(n.value)
        if isinstance(n,ast.Name):
            if n.id not in variables: raise ValueError(f"متغیر تعریف نشده: {n.id}")
            value=float(variables[n.id])
            if not math.isfinite(value): raise ValueError("مقدار متغیر باید متناهی باشد")
            return value
        if isinstance(n,ast.UnaryOp) and type(n.op) in _OP: return _OP[type(n.op)](ev(n.operand))
        if isinstance(n,ast.BinOp) and type(n.op) in _OP:
            try: result=_OP[type(n.op)](ev(n.left),ev(n.right))
            except ZeroDivisionError as exc: raise ValueError("تقسیم بر صفر مجاز نیست") from exc
            if not math.isfinite(result): raise ValueError("نتیجه فرمول باید متناهی باشد")
            return result
        raise ValueError("فرمول شامل عملگر یا مقدار غیرمجاز است")
    result=ev(tree)
    if not math.isfinite(result): raise ValueError("نتیجه فرمول باید متناهی باشد")
    return result
