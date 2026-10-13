"""Bounded AST formula evaluation using existing exact numeric utilities."""
from __future__ import annotations
import ast,operator
from core.commercial.exact_values import number,wire,exact
from core.takeoff.units import normalize_unit
_OP={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.Pow:operator.pow}

@exact
def evaluate(expression,variables):
    source=str(expression)
    if len(source)>4096:raise ValueError('فرمول بیش از حد طولانی است')
    try:tree=ast.parse(source,mode='eval')
    except (SyntaxError,ValueError,RecursionError) as e:raise ValueError('فرمول نامعتبر است') from e
    if sum(1 for _ in ast.walk(tree))>256:raise ValueError('پیچیدگی فرمول بیش از حد مجاز است')
    def ev(n):
        if isinstance(n,ast.Expression):return ev(n.body)
        if isinstance(n,ast.Constant) and isinstance(n.value,(int,float)) and not isinstance(n.value,bool):
            return number(ast.get_source_segment(source,n),'عدد فرمول',True)
        if isinstance(n,ast.Name):
            if n.id not in variables:raise ValueError(f'متغیر تعریف نشده: {n.id}')
            return number(variables[n.id],'متغیر '+n.id,True)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):
            value=ev(n.operand);return -value if isinstance(n.op,ast.USub) else value
        if isinstance(n,ast.BinOp) and type(n.op) in _OP:
            left,right=ev(n.left),ev(n.right)
            if isinstance(n.op,ast.Pow) and (right!=right.to_integral_value() or abs(right)>32):raise ValueError('توان فرمول باید صحیح و در محدوده مجاز باشد')
            if isinstance(n.op,ast.Div) and right==0:raise ValueError('تقسیم بر صفر مجاز نیست')
            if isinstance(n.op,ast.Pow) and left==0 and right<0:raise ValueError('تقسیم بر صفر مجاز نیست')
            return _OP[type(n.op)](left,right)
        raise ValueError('فرمول شامل عملگر یا مقدار غیرمجاز است')
    return wire(ev(tree))


def evaluate_rows(rows):
    """Recalculate the complete reference graph atomically; no unknown row is zero.

    References are additive quantities of the declared same unit. Products of
    two referenced quantities are blocked pending explicit dimensional detail.
    """
    if not isinstance(rows,dict) or len(rows)>1000:raise ValueError('ساختار یا تعداد ردیف‌های فرمول نامعتبر است')
    values={};active=set()
    def calc(key):
        if key in values:return values[key]
        if key in active:raise ValueError('وابستگی حلقوی در فرمول‌ها')
        if key not in rows:raise ValueError('ردیف مرجع معتبر یافت نشد')
        active.add(key);row=rows[key];unit=normalize_unit(row['unit']);refs=row.get('references',{})
        variables=dict(row.get('variables',{}))
        for name,target in refs.items():
            if name in variables:raise ValueError('نام پارامتر و مرجع تکراری است')
            if target not in rows:raise ValueError('ردیف مرجع معتبر یافت نشد')
            if normalize_unit(rows[target]['unit'])!=unit:raise ValueError('واحد ردیف‌های مرجع ناسازگار است')
            variables[name]=calc(target)
        try:tree=ast.parse(row['expression'],mode='eval')
        except (SyntaxError,ValueError) as e:raise ValueError('فرمول نامعتبر است') from e
        for node in ast.walk(tree):
            if isinstance(node,ast.BinOp) and isinstance(node.op,(ast.Mult,ast.Div,ast.Pow)):
                names=lambda part:{n.id for n in ast.walk(part) if isinstance(n,ast.Name)} & set(refs)
                if names(node.left) and names(node.right) or isinstance(node.op,ast.Pow) and names(node.left) or isinstance(node.op,ast.Div) and names(node.right):
                    raise ValueError('واحد نتیجه ضرب یا توان مراجع نیازمند دیتایل صریح است')
        value=evaluate(row['expression'],variables);active.remove(key);values[key]=value;return value
    try:
        for key in rows:calc(key)
    except RecursionError as e:raise ValueError('عمق وابستگی فرمول بیش از حد مجاز است') from e
    return values
