"""Explicit geometric deductions through the existing formula revision command."""
import ast
from copy import deepcopy
from core.commercial.exact_values import number,wire,exact
from core.takeoff.formulas import evaluate_rows,evaluate
from core.takeoff.manual_formula_register import load,save,clean,text,revision

@exact
def summary(service,pid,key):
    reg=load(service,pid);row=reg[key];d=row['data'];variables=deepcopy(d['variables'])
    for item in d['deductions']:variables[item.get('variable',item['id'])]='0'
    values=evaluate_rows({k:{'expression':v['data']['expression'],'variables':v['data']['variables'],'references':v['data']['references'],'unit':v['data']['unit']} for k,v in reg.items()})
    variables.update({name:values[target] for name,target in d['references'].items()});gross=number(evaluate(d['expression'],variables),'مقدار پیش از کسر');net=number(row['quantity'],'خالص')
    return wire({'gross':gross,'net':net,'deducted':gross-net,'unit':d['unit']})

def change_data(data,item=None,remove_id=None):
    d=deepcopy(data);sid=text(remove_id if remove_id is not None else item.get('id'),'شناسه منبع کسر');old=next((v for v in d['deductions'] if v['id']==sid),None)
    if remove_id is not None:
        if old is None:raise ValueError('کسر موردنظر وجود ندارد')
        variable=old.get('variable',old['id'])
        class Remove(ast.NodeTransformer):
            def visit_BinOp(self,node):
                node=self.generic_visit(node)
                if isinstance(node.op,ast.Sub) and isinstance(node.right,ast.Name) and node.right.id==variable:return node.left
                return node
        tree=Remove().visit(ast.parse(d['expression'],mode='eval'));d['expression']=ast.unparse(tree);d['variables'].pop(variable,None);d['deductions']=[v for v in d['deductions'] if v['id']!=sid]
    else:
        item=deepcopy(item);text(item.get('source_id'),'منبع هندسی کسر');variable=text(item.get('variable'),'نام پارامتر کسر')
        if item['source_id']!=sid:raise ValueError('شناسه کسر باید همان هویت هندسی صریح باشد')
        if old and (old.get('variable',old['id'])!=variable or old.get('source_id',sid)!=item['source_id']):raise ValueError('هویت و نام پارامتر کسر در ویرایش ثابت است')
        if not variable.isidentifier() or variable in d['references']:raise ValueError('نام پارامتر کسر نامعتبر است')
        if not old and variable in d['variables']:raise ValueError('نام کسر با پارامتر موجود تداخل دارد')
        if not old:d['expression']='('+d['expression']+')-'+variable
        d['variables'][variable]=item['quantity'];d['deductions']=[v for v in d['deductions'] if v['id']!=sid]+[item]
    return clean(d)

def set_item(service,pid,key,item,*,expected_revision,reason):
    row=load(service,pid)[key];revision(expected_revision,row['revision'])
    if row['status']=='committed':raise ValueError('کسر ردیف قطعی فقط از مسیر اصلاحیه مستقل تغییر می‌کند')
    return save(service,pid,key,change_data(row['data'],item),expected_revision=expected_revision,reason=reason)

def remove(service,pid,key,sid,*,expected_revision,reason):
    row=load(service,pid)[key];revision(expected_revision,row['revision'])
    if row['status']=='committed':raise ValueError('حذف کسر قطعی فقط از مسیر اصلاحیه مستقل مجاز است')
    return save(service,pid,key,change_data(row['data'],remove_id=sid),expected_revision=expected_revision,reason=reason)
