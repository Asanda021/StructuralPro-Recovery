"""Bounded AST formula evaluation using existing exact numeric utilities."""
from __future__ import annotations
import ast,operator
from core.commercial.exact_values import number,wire,exact
from core.takeoff.units import normalize_unit
_OP={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.Pow:operator.pow}

@exact
def evaluate(expression,variables,*,variable_units=None,output_unit=None):
    source=str(expression)
    if len(source)>4096:raise ValueError('فرمول بیش از حد طولانی است')
    try:tree=ast.parse(source,mode='eval')
    except (SyntaxError,ValueError,RecursionError) as e:raise ValueError('فرمول نامعتبر است') from e
    if sum(1 for _ in ast.walk(tree))>256:raise ValueError('پیچیدگی فرمول بیش از حد مجاز است')
    typed=variable_units is not None
    if typed:
        from core.takeoff.units import unit_contract
        if not isinstance(variable_units,dict) or set(variable_units)!=set(variables):raise ValueError('واحد ساختاریافته همه پارامترها باید صریح باشد')
        contracts={k:unit_contract(v) for k,v in variable_units.items()}
        output_dimension,output_scale=unit_contract(output_unit)
    scalar=(0,0,0)
    def ev(n):
        if isinstance(n,ast.Expression):return ev(n.body)
        if isinstance(n,ast.Constant) and isinstance(n.value,(int,float)) and not isinstance(n.value,bool):
            value=number(ast.get_source_segment(source,n),'عدد فرمول',True)
            return (value,scalar) if typed else value
        if isinstance(n,ast.Name):
            if n.id not in variables:raise ValueError(f'متغیر تعریف نشده: {n.id}')
            value=number(variables[n.id],'متغیر '+n.id,True)
            return (value*contracts[n.id][1],contracts[n.id][0]) if typed else value
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):
            value=ev(n.operand)
            if typed:return (-value[0] if isinstance(n.op,ast.USub) else value[0],value[1])
            return -value if isinstance(n.op,ast.USub) else value
        if isinstance(n,ast.BinOp) and type(n.op) in _OP:
            left,right=ev(n.left),ev(n.right)
            if typed:
                (left,ld),(right,rd)=left,right
                if isinstance(n.op,(ast.Add,ast.Sub)):
                    if ld!=rd:raise ValueError('جمع یا تفریق واحدهای ناهم‌بُعد مجاز نیست')
                    result_dimension=ld
                elif isinstance(n.op,ast.Mult):result_dimension=tuple(a+b for a,b in zip(ld,rd))
                elif isinstance(n.op,ast.Div):result_dimension=tuple(a-b for a,b in zip(ld,rd))
                else:
                    if rd!=scalar or right!=right.to_integral_value() or abs(right)>32:raise ValueError('توان باید صحیح و بدون بُعد باشد')
                    result_dimension=tuple(a*int(right) for a in ld)
                if any(abs(v)>32 for v in result_dimension):raise ValueError('بُعد نتیجه بیش از محدوده مجاز است')
            if isinstance(n.op,ast.Pow) and (right!=right.to_integral_value() or abs(right)>32):raise ValueError('توان فرمول باید صحیح و در محدوده مجاز باشد')
            if isinstance(n.op,ast.Div) and right==0:raise ValueError('تقسیم بر صفر مجاز نیست')
            if isinstance(n.op,ast.Pow) and left==0 and right<0:raise ValueError('تقسیم بر صفر مجاز نیست')
            value=_OP[type(n.op)](left,right)
            return (value,result_dimension) if typed else value
        raise ValueError('فرمول شامل عملگر یا مقدار غیرمجاز است')
    result=ev(tree)
    if typed:
        value,dim=result
        if dim!=output_dimension:raise ValueError('بُعد نتیجه فرمول با واحد خروجی ناسازگار است')
        return wire(value/output_scale)
    return wire(result)


def evaluate_rows(rows):
    """Recalculate the complete reference graph atomically; no unknown row is zero.

    Versioned typed rows check dimensions and exact scale conversions in the
    same AST evaluator. Historical untyped rows keep their previous bounded
    evaluator for read/recovery; orchestration blocks new untyped writes/reviews.
    """
    if not isinstance(rows,dict) or len(rows)>1000:raise ValueError('ساختار یا تعداد ردیف‌های فرمول نامعتبر است')
    values={};active=set()
    def calc(key):
        if key in values:return values[key]
        if key in active:raise ValueError('وابستگی حلقوی در فرمول‌ها')
        if key not in rows:raise ValueError('ردیف مرجع معتبر یافت نشد')
        active.add(key);row=rows[key];unit=normalize_unit(row['unit']);refs=row.get('references',{})
        variables=dict(row.get('variables',{}))
        typed='variable_units' in row or 'unit_policy' in row
        units=dict(row.get('variable_units',{}))
        if typed and (row.get('unit_policy')!='dimensional_decimal_v1' or set(units)!=set(variables)):raise ValueError('قرارداد نسخه‌دار واحد همه پارامترها ضروری است')
        for name,target in refs.items():
            if name in variables:raise ValueError('نام پارامتر و مرجع تکراری است')
            if target not in rows:raise ValueError('ردیف مرجع معتبر یافت نشد')
            if typed:
                if rows[target].get('unit_policy')!='dimensional_decimal_v1':raise ValueError('مرجع تاریخی نیازمند تعیین صریح واحد و بازبینی است')
                units[name]=normalize_unit(rows[target]['unit'])
            elif normalize_unit(rows[target]['unit'])!=unit:raise ValueError('واحد ردیف‌های مرجع ناسازگار است')
            variables[name]=calc(target)
        try:tree=ast.parse(row['expression'],mode='eval')
        except (SyntaxError,ValueError) as e:raise ValueError('فرمول نامعتبر است') from e
        for node in (() if typed else ast.walk(tree)):
            if isinstance(node,ast.BinOp) and isinstance(node.op,(ast.Mult,ast.Div,ast.Pow)):
                names=lambda part:{n.id for n in ast.walk(part) if isinstance(n,ast.Name)} & set(refs)
                if names(node.left) and names(node.right) or isinstance(node.op,ast.Pow) and names(node.left) or isinstance(node.op,ast.Div) and names(node.right):
                    raise ValueError('واحد نتیجه ضرب یا توان مراجع نیازمند دیتایل صریح است')
        value=evaluate(row['expression'],variables,variable_units=units,output_unit=unit) if typed else evaluate(row['expression'],variables);active.remove(key);values[key]=value;return value
    try:
        for key in rows:calc(key)
    except RecursionError as e:raise ValueError('عمق وابستگی فرمول بیش از حد مجاز است') from e
    return values
