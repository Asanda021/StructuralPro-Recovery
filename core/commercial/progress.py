"""Validated period progress; exact monetary and quantity arithmetic."""
from decimal import Decimal
from core.commercial.exact_values import number,wire,exact,display_percent

@exact
def build_progress(lines, *, deductions=None, payments=None):
    rows=[];contract_total=completed_total=current_total=Decimal(0);seen=set()
    deduction_values=[number(x,'کسور') for x in (deductions or [])]
    payment_values=[number(x,'پرداخت') for x in (payments or [])]
    for x in lines:
        d=x if isinstance(x,dict) else vars(x)
        code=str(d.get('code') or d.get('price_code') or d.get('source') or '').strip()
        if code and code in seen:raise ValueError(f'duplicate progress line: {code}')
        if code:seen.add(code)
        cq=number(d.get('contract_quantity',0),'مقدار قرارداد');prev=number(d.get('previous_quantity',0),'کارکرد قبلی')
        cur=number(d.get('current_quantity',0),'کارکرد دوره');price=number(d.get('unit_price',0),'بهای واحد')
        if prev>cq or cur>cq-prev:raise ValueError(f'progress exceeds contract for {code or "line"}')
        cumulative=prev+cur;contract_amount=cq*price;completed_amount=cumulative*price;current_amount=cur*price
        rows.append({**d,'cumulative_quantity':cumulative,'remaining_quantity':cq-cumulative,
            'progress_percent':display_percent(cumulative,cq),'contract_amount':contract_amount,
            'current_amount':current_amount,'completed_amount':completed_amount,'over_contract_quantity':0})
        contract_total+=contract_amount;completed_total+=completed_amount;current_total+=current_amount
    deduction_total=sum(deduction_values,Decimal(0));payment_total=sum(payment_values,Decimal(0))
    payable=max(current_total-deduction_total,Decimal(0))
    return wire({'lines':rows,'contract_total':contract_total,'completed_total':completed_total,
        'current_total':current_total,'gross_current':current_total,'deductions':deduction_total,'payable_current':payable,
        'payments':payment_total,'balance_current':payable-payment_total,'remaining_contract':contract_total-completed_total,
        'progress_percent':display_percent(completed_total,contract_total)})
