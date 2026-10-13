"""Commercial payment statement with transparent contractual deductions."""
from __future__ import annotations
from typing import Iterable
from core.commercial.exact_values import number,wire,exact
from core.projects.statement_engine import StatementLine,build_statement

@exact
def build_payment_statement(contract,current:Iterable[StatementLine],*,previous_paid=0.0,
                            advance_recovery_rate=0.0,other_deduction_rate=0.0):
    errors=contract.validate()
    if errors: raise ValueError("; ".join(errors))
    base=build_statement(current,retention_rate=contract.retention_rate,
        advance_recovery_rate=advance_recovery_rate,
        other_deduction_rate=other_deduction_rate,advance_paid=contract.advance_paid)
    gross=number(base['gross_current'],'gross_current');commercial_base=contract.commercial_total(gross)
    tax=commercial_base*number(contract.tax_rate,'tax');insurance=commercial_base*number(contract.insurance_rate,'insurance')
    payable=number(base['payable'],'payable',True)+tax-insurance;paid=number(previous_paid,'previous_paid')
    return wire({**base,'contract_id':contract.contract_id,'contract_total':contract.total(),
        'commercial_base_current':gross,'commercial_total_current':commercial_base,'tax':tax,'insurance':insurance,'payable':payable,
        'previous_paid':paid,'balance_after_current':contract.commercial_total()-paid-payable,
        'financial_policy_status':'LEGACY_PREVIEW_NOT_FINANCIALLY_APPROVED',
        'commercial_factors':{'overhead_rate':contract.overhead_rate,'regional_rate':contract.regional_rate,
            'retention_rate':contract.retention_rate,'tax_rate':contract.tax_rate,'insurance_rate':contract.insurance_rate}})

class PaymentStatement:
    def __init__(self,contract): self.contract=contract
    def build(self,lines,**kwargs): return build_payment_statement(self.contract,lines,**kwargs)
